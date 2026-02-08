"""
零售贷款智能运营的 MCP 工具：供 Agent 调用加载数据、训练、推荐、预测等。
使用 claude_agent_sdk 的 @tool 与 create_sdk_mcp_server，与 Ollama 主 Agent 配合。
"""
from __future__ import annotations

import os
from typing import Any

# 全局会话状态：当前进程内一次对话共享
_state: dict[str, Any] = {
    "datasets": None,
    "propensity_model": None,
    "recommendation_model": None,
}


def _get_state():
    return _state


def set_ui_state(datasets=None, propensity_model=None, recommendation_model=None):
    """供 Gradio UI 在加载数据或训练后同步状态，使 Agent 与界面共享同一数据/模型。"""
    s = _get_state()
    if datasets is not None:
        s["datasets"] = datasets
    if propensity_model is not None:
        s["propensity_model"] = propensity_model
    if recommendation_model is not None:
        s["recommendation_model"] = recommendation_model


def _ensure_datasets():
    """若未加载数据则加载（同步，供工具内调用）。"""
    state = _get_state()
    if state["datasets"] is not None:
        return state["datasets"]
    os.environ.setdefault("DISABLE_PANDERA_IMPORT_WARNING", "True")
    from app.data_prep import prepare_datasets
    state["datasets"] = prepare_datasets(size="100k")
    return state["datasets"]


def _ensure_models():
    """若未训练则先加载数据再训练（同步）。"""
    state = _get_state()
    if state["propensity_model"] is not None and state["recommendation_model"] is not None:
        return state["propensity_model"], state["recommendation_model"]
    from app.data_prep import prepare_datasets
    from app.model_training import train_propensity_model, train_recommendation_model
    if state["datasets"] is None:
        state["datasets"] = prepare_datasets(size="100k")
    interactions, user_profiles, item_profiles = state["datasets"]
    state["propensity_model"] = train_propensity_model(interactions, user_profiles, item_profiles)
    state["recommendation_model"] = train_recommendation_model(interactions)
    return state["propensity_model"], state["recommendation_model"]


def _build_feature_row(user_row, item_row, recency_lookup):
    """构建单条特征用于意愿预测。"""
    import pandas as pd
    user_id = user_row["user_id"]
    recent_value = recency_lookup.loc[user_id, "recent_interaction"] if user_id in recency_lookup.index else 0.5
    overlap = len(set(user_row["top_tags"]).intersection(set(item_row["product_tags"])))
    return pd.Series({
        "asset_score": user_row["asset_score"],
        "user_risk_score": user_row["user_risk_score"],
        "item_risk_score": item_row["item_risk_score"],
        "genre_overlap": overlap,
        "risk_gap": user_row["user_risk_score"] - item_row["item_risk_score"],
        "recent_interaction": recent_value,
        "asset_label": user_row["asset_label"],
        "user_risk_label": user_row["user_risk_label"],
        "item_risk_label": item_row["item_risk_label"],
    })


def _compute_recency(interactions):
    import pandas as pd
    max_ts = interactions["timestamp"].max()
    agg = interactions.groupby("user_id")["timestamp"].max().to_frame()
    agg["recent_interaction"] = agg["timestamp"] / max_ts
    return agg[["recent_interaction"]]


def _text_content(text: str) -> list:
    return [{"type": "text", "text": text}]


async def tool_load_data(args: dict) -> dict:
    """加载示例数据（MovieLens 100k 转贷款场景）。无需参数。"""
    try:
        datasets = _ensure_datasets()
        interactions, user_profiles, item_profiles = datasets
        n_inter = len(interactions)
        n_users = user_profiles["user_id"].nunique()
        n_items = item_profiles["item_id"].nunique()
        msg = (
            f"数据已加载。交互记录: {n_inter:,} 条，客户数: {n_users:,}，贷款产品数: {n_items:,}。"
            " 可继续使用「训练模型」或「推荐」等工具。"
        )
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"加载数据失败: {e}")}


async def tool_train_models(args: dict) -> dict:
    """基于当前已加载数据训练贷款意愿模型与推荐模型。无需参数。若未加载数据会先自动加载。"""
    try:
        propensity, recommender = _ensure_models()
        auc = propensity.roc_auc
        perf = propensity.training_summary.get("performance", {})
        msg = (
            f"训练完成。贷款意愿模型 ROC-AUC: {auc:.3f}；"
            f"准确率: {perf.get('准确率', 0):.1%}，精确率: {perf.get('精确率', 0):.1%}，"
            f"召回率: {perf.get('召回率', 0):.1%}，F1: {perf.get('F1 分数', 0):.1%}。"
            " 可使用「推荐」或「预测意愿」工具。"
        )
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"训练失败: {e}")}


async def tool_get_data_summary(args: dict) -> dict:
    """查看当前数据概况（交互数、客户数、产品数）。若无数据会先加载。"""
    try:
        datasets = _ensure_datasets()
        interactions, user_profiles, item_profiles = datasets
        n_inter = len(interactions)
        n_users = user_profiles["user_id"].nunique()
        n_items = item_profiles["item_id"].nunique()
        msg = f"当前数据：交互记录 {n_inter:,} 条，客户 {n_users:,} 人，贷款产品 {n_items:,} 个。"
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"获取概况失败: {e}")}


async def tool_recommend(args: dict) -> dict:
    """为指定客户做个性化贷款推荐。参数：user_id（客户ID，字符串），top_k（推荐数量，默认5）。"""
    try:
        user_id = str(args.get("user_id", ""))
        top_k = int(args.get("top_k", 5))
        if not user_id:
            return {"content": _text_content("请提供 user_id 参数。")}
        propensity, recommender = _ensure_models()
        state = _get_state()
        _, user_profiles, item_profiles = state["datasets"]
        interactions = state["datasets"][0]
        recency_lookup = _compute_recency(interactions)
        user_rows = user_profiles[user_profiles["user_id"] == user_id]
        if user_rows.empty:
            return {"content": _text_content(f"未找到客户 {user_id}，请使用数据中的有效客户ID。")}
        user_row = user_rows.iloc[0]
        rec_df = recommender.recommend(user_id, top_k=top_k)
        rec_df = rec_df.merge(item_profiles, on="item_id", how="left")
        lines = []
        for idx, (_, item) in enumerate(rec_df.iterrows(), 1):
            feature_row = _build_feature_row(user_row, item, recency_lookup)
            prob = float(propensity.predict_proba(feature_row.to_frame().T)[0])
            lines.append(
                f"{idx}. {item.get('title', item['item_id'])} | 推荐得分: {item.get('prediction', 0):.3f} | 贷款意愿概率: {prob:.3f}"
            )
        msg = "推荐结果：\n" + "\n".join(lines) if lines else "暂无推荐结果。"
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"推荐失败: {e}")}


async def tool_predict_propensity(args: dict) -> dict:
    """预测某客户对某贷款产品的申请意愿概率。参数：user_id（客户ID），item_id（产品ID）。"""
    try:
        user_id = str(args.get("user_id", ""))
        item_id = args.get("item_id")
        if item_id is not None:
            item_id = int(item_id)
        if not user_id or item_id is None:
            return {"content": _text_content("请提供 user_id 和 item_id 参数。")}
        propensity, _ = _ensure_models()
        state = _get_state()
        interactions, user_profiles, item_profiles = state["datasets"]
        recency_lookup = _compute_recency(interactions)
        user_rows = user_profiles[user_profiles["user_id"] == user_id]
        item_rows = item_profiles[item_profiles["item_id"] == item_id]
        if user_rows.empty or item_rows.empty:
            return {"content": _text_content("未找到该客户或产品，请使用数据中的有效ID。")}
        user_row = user_rows.iloc[0]
        item_row = item_rows.iloc[0]
        feature_row = _build_feature_row(user_row, item_row, recency_lookup)
        prob = float(propensity.predict_proba(feature_row.to_frame().T)[0])
        from app.model_training import describe_feature, top_feature_contributions
        contribs = propensity.explain_instance(feature_row)
        top = top_feature_contributions(contribs, top_k=5)
        expl = "; ".join(describe_feature(n, v) for n, v in top)
        msg = f"客户 {user_id} 对产品 {item_id} 的贷款意愿概率: {prob:.3f}。主要影响因素: {expl}"
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"预测失败: {e}")}


async def tool_similar_items(args: dict) -> dict:
    """查找与某贷款产品相似的其他产品。参数：item_id（产品ID），top_k（数量，默认5）。"""
    try:
        item_id = args.get("item_id")
        if item_id is not None:
            item_id = int(item_id)
        top_k = int(args.get("top_k", 5))
        if item_id is None:
            return {"content": _text_content("请提供 item_id 参数。")}
        _, recommender = _ensure_models()
        state = _get_state()
        _, _, item_profiles = state["datasets"]
        similar_df = recommender.similar_items(item_id, top_k=top_k)
        similar_df = similar_df.merge(item_profiles, on="item_id", how="left")
        titles = similar_df["title"].fillna("").tolist() if not similar_df.empty else []
        msg = "相似产品: " + ", ".join(titles) if titles else "暂无相似产品。"
        return {"content": _text_content(msg)}
    except Exception as e:
        return {"content": _text_content(f"查询失败: {e}")}


def build_loan_agent_mcp_server():
    """创建零售贷款 MCP 服务，供 ClaudeAgentOptions.mcp_servers 使用。"""
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server
    except ImportError:
        return None

    load_data_tool = tool(
        "load_data",
        "加载示例贷款场景数据（MovieLens 100k 转贷款）。无参数。",
        {},
    )(tool_load_data)
    train_tool = tool(
        "train_models",
        "训练贷款意愿模型与推荐模型。无参数；若未加载数据会先自动加载。",
        {},
    )(tool_train_models)
    summary_tool = tool(
        "get_data_summary",
        "查看当前数据概况（交互数、客户数、产品数）。无参数。",
        {},
    )(tool_get_data_summary)
    recommend_tool = tool(
        "recommend",
        "为指定客户做个性化贷款推荐。参数: user_id（客户ID）, top_k（推荐数量，默认5）。",
        {"user_id": str, "top_k": int},
    )(tool_recommend)
    predict_tool = tool(
        "predict_propensity",
        "预测某客户对某贷款产品的申请意愿概率。参数: user_id, item_id。",
        {"user_id": str, "item_id": int},
    )(tool_predict_propensity)
    similar_tool = tool(
        "similar_items",
        "查找与某贷款产品相似的其他产品。参数: item_id, top_k（默认5）。",
        {"item_id": int, "top_k": int},
    )(tool_similar_items)

    return create_sdk_mcp_server(
        name="loan_agent",
        version="1.0.0",
        tools=[load_data_tool, train_tool, summary_tool, recommend_tool, predict_tool, similar_tool],
    )


def get_loan_agent_allowed_tools() -> list[str]:
    """返回 loan_agent MCP 工具在 allowed_tools 中的名称。"""
    return [
        "mcp__loan_agent__load_data",
        "mcp__loan_agent__train_models",
        "mcp__loan_agent__get_data_summary",
        "mcp__loan_agent__recommend",
        "mcp__loan_agent__predict_propensity",
        "mcp__loan_agent__similar_items",
    ]
