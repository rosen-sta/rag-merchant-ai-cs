import re
from typing import Dict, Optional


ORDER_NOT_FOUND_MESSAGE = "没有查询到该订单，建议确认订单号是否正确，或联系人工客服处理。"

ORDER_QUERY_KEYWORDS = [
    "订单",
    "订单号",
    "发货了吗",
    "到哪了",
    "物流",
    "快递",
    "签收",
    "运输中",
]

AFTERSALE_KEYWORDS = [
    "我要退货",
    "我要换货",
    "我要退款",
    "商品坏了",
    "质量问题",
    "破损",
    "少件",
    "没收到",
    "投诉",
    "物流异常",
    "退款失败",
]


def extract_order_no(question: str) -> str:
    match = re.search(r"(?<!\d)(\d{4,})(?!\d)", question)
    return match.group(1) if match else ""


def is_order_query(question: str) -> bool:
    order_no = extract_order_no(question)
    if order_no and any(keyword in question for keyword in ORDER_QUERY_KEYWORDS):
        return True
    return bool(order_no and "订单" in question)


def is_aftersale_request(question: str) -> bool:
    return any(keyword in question for keyword in AFTERSALE_KEYWORDS)


def infer_issue_type(question: str) -> str:
    if "投诉" in question:
        return "投诉"
    if "退货" in question:
        if any(keyword in question for keyword in ["质量问题", "商品坏了", "破损", "少件"]):
            return "质量问题"
        return "退货"
    if "退款" in question or "退款失败" in question:
        return "退款"
    if "换货" in question:
        return "换货"
    if any(keyword in question for keyword in ["质量问题", "商品坏了", "破损", "少件"]):
        return "质量问题"
    if any(keyword in question for keyword in ["物流异常", "没收到", "物流一直没更新"]):
        return "物流问题"
    return "其他"


def order_to_card(order: Dict) -> Dict:
    return {
        "order_no": order.get("order_no", ""),
        "customer_name": order.get("customer_name", ""),
        "product_name": order.get("product_name", ""),
        "order_status": order.get("order_status", ""),
        "shipping_status": order.get("shipping_status", ""),
        "tracking_no": order.get("tracking_no", ""),
        "express_company": order.get("express_company", ""),
        "paid_amount": order.get("paid_amount", ""),
        "created_at": order.get("created_at", ""),
        "shipped_at": order.get("shipped_at", ""),
        "aftersale_status": order.get("aftersale_status", ""),
    }


def aftersale_ticket_to_card(ticket: Dict) -> Dict:
    return {
        "id": ticket.get("id"),
        "ticket_no": ticket.get("ticket_no", ""),
        "order_no": ticket.get("order_no", ""),
        "issue_type": ticket.get("issue_type", ""),
        "issue_description": ticket.get("issue_description", ""),
        "status": ticket.get("status", ""),
        "needs_human": bool(ticket.get("needs_human")),
        "created_at": ticket.get("created_at", ""),
    }


def build_order_answer(order: Optional[Dict], question: str = "") -> str:
    if not order:
        return ORDER_NOT_FOUND_MESSAGE
    order_no = order.get("order_no", "")
    order_status = order.get("order_status", "")
    shipping_status = order.get("shipping_status", "")
    company = order.get("express_company", "")
    tracking_no = order.get("tracking_no", "")
    shipped_at = order.get("shipped_at", "")

    if order_status == "已取消":
        return f"亲，订单 {order_no} 当前状态是已取消，暂时没有发货和物流信息。"
    if shipping_status in {"待发货", "未发货"} or not tracking_no:
        return (
            f"亲，订单 {order_no} 目前{order_status or '已创建'}，暂未发货。"
            "店铺默认付款后 48 小时内发货，如超过时间仍未发出，建议联系人工客服确认。"
        )

    shipped_text = f"，发货时间是{shipped_at}" if shipped_at else ""
    return (
        f"亲，订单 {order_no} 已经发货，目前物流状态是{shipping_status}{shipped_text}。"
        f"快递公司为{company or '暂无'}，单号是 {tracking_no}，您可以留意后续物流更新哦。"
    )


def build_ai_suggestion(issue_type: str, order: Optional[Dict]) -> str:
    if issue_type == "质量问题":
        return "建议人工客服核实商品照片、破损位置、签收时间和退换货方式。"
    if issue_type in {"退货", "换货"}:
        return "建议人工客服核实订单状态、商品是否影响二次销售，并确认退换货地址。"
    if issue_type == "退款":
        return "建议人工客服核实订单售后状态、退款渠道和到账时效。"
    if issue_type == "物流问题":
        return "建议人工客服核实快递轨迹、是否签收异常，并联系快递公司进一步确认。"
    if issue_type == "投诉":
        return "建议人工客服优先跟进，核实顾客诉求并给出明确处理时限。"
    if order:
        return "建议人工客服结合订单状态进一步确认处理方案。"
    return "建议人工客服进一步核实具体情况后处理。"


def build_aftersale_answer(ticket: Dict) -> str:
    issue_type = ticket.get("issue_type", "其他")
    order_no = ticket.get("order_no", "")
    order_text = f"订单 {order_no} " if order_no else ""
    return (
        f"亲，已经帮您记录{order_text}售后申请。"
        f"该问题属于{issue_type}，建议由人工客服进一步核实具体情况、凭证和处理方式。"
        "请保持联系方式畅通。"
    )


def order_context(order: Dict) -> str:
    return "\n".join(
        [
            f"订单号：{order.get('order_no', '')}",
            f"顾客昵称：{order.get('customer_name', '')}",
            f"商品名称：{order.get('product_name', '')}",
            f"订单状态：{order.get('order_status', '')}",
            f"物流状态：{order.get('shipping_status', '')}",
            f"快递公司：{order.get('express_company', '')}",
            f"快递单号：{order.get('tracking_no', '')}",
            f"支付金额：{order.get('paid_amount', '')}",
            f"下单时间：{order.get('created_at', '')}",
            f"发货时间：{order.get('shipped_at', '')}",
            f"售后状态：{order.get('aftersale_status', '')}",
        ]
    )


def ticket_context(ticket: Dict) -> str:
    return "\n".join(
        [
            f"工单编号：{ticket.get('ticket_no', '')}",
            f"订单号：{ticket.get('order_no', '')}",
            f"问题类型：{ticket.get('issue_type', '')}",
            f"问题描述：{ticket.get('issue_description', '')}",
            f"AI建议：{ticket.get('ai_suggestion', '')}",
            f"状态：{ticket.get('status', '')}",
        ]
    )
