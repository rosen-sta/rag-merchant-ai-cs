const h = React.createElement;
const { useEffect, useMemo, useRef, useState } = React;

const NAV_ITEMS = [
  { path: "/dashboard", label: "后台首页" },
  { path: "/products", label: "商品管理" },
  { path: "/orders", label: "订单管理" },
  { path: "/knowledge", label: "知识库管理" },
  { path: "/test", label: "AI 客服测试" },
  { path: "/aftersales", label: "售后工单" },
  { path: "/chat-records", label: "聊天记录" },
  { path: "/missed", label: "未命中问题" },
  { path: "/customer", label: "顾客端预览" },
];

const SAMPLE_QUESTIONS = [
  "这件防晒衬衫适合夏天通勤穿吗？",
  "多久发货？",
  "可以退货吗？",
  "这款适合学生党吗？",
  "有 200 元以内的包推荐吗？",
  "防晒衬衫和通勤托特包有什么区别？",
  "订单 10001 发货了吗？",
  "订单 10003 商品有质量问题，我要退货",
  "质量问题怎么处理？",
];

function routeFromHash() {
  const route = window.location.hash.replace(/^#/, "");
  return route || "/dashboard";
}

function navigate(path) {
  window.location.hash = path;
}

function makeSessionId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
}

function getCustomerSessionId() {
  const key = "customer-session-id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created = makeSessionId("customer");
  localStorage.setItem(key, created);
  return created;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = data && data.detail ? data.detail : "请求失败";
    throw new Error(message);
  }
  return data;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function App() {
  const [route, setRoute] = useState(routeFromHash());
  const [auth, setAuth] = useState(() => localStorage.getItem("merchant-auth") || "");

  useEffect(() => {
    const onHashChange = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!auth && route !== "/customer" && route !== "/login") {
      navigate("/login");
    }
  }, [auth, route]);

  const isCustomerPage = route === "/customer";
  if (!auth && route !== "/customer") {
    return h(LoginPage, { onLogin: setAuth });
  }

  return h(
    "div",
    { className: isCustomerPage ? "customer-shell" : "app-shell" },
    !isCustomerPage &&
      h(Sidebar, {
        route,
        onLogout: () => {
          localStorage.removeItem("merchant-auth");
          setAuth("");
          navigate("/login");
        },
      }),
    h(
      "main",
      { className: isCustomerPage ? "customer-main" : "main-content" },
      !isCustomerPage && h(Topbar, { route }),
      h(PageRouter, { route, auth })
    )
  );
}

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiRequest("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem("merchant-auth", data.token);
      onLogin(data.token);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return h(
    "main",
    { className: "login-page" },
    h(
      "section",
      { className: "login-panel" },
      h("div", { className: "brand-mark" }, "RAG"),
      h("h1", null, "电商商家 AI 客服导购系统"),
      h(
        "form",
        { onSubmit: submit, className: "login-form" },
        h(LabeledInput, { label: "账号", value: username, onChange: setUsername, autoFocus: true }),
        h(LabeledInput, { label: "密码", value: password, onChange: setPassword, type: "password" }),
        error && h("div", { className: "form-error" }, error),
        h("button", { className: "primary-btn", disabled: loading }, loading ? "登录中..." : "登录")
      )
    )
  );
}

function LabeledInput({ label, value, onChange, type = "text", autoFocus = false }) {
  return h(
    "label",
    { className: "field" },
    h("span", null, label),
    h("input", {
      type,
      value,
      autoFocus,
      onChange: (event) => onChange(event.target.value),
    })
  );
}

function Sidebar({ route, onLogout }) {
  return h(
    "aside",
    { className: "sidebar" },
    h("div", { className: "sidebar-title" }, h("span", { className: "small-logo" }, "R"), h("strong", null, "商家后台")),
    h(
      "nav",
      { className: "sidebar-nav" },
      NAV_ITEMS.map((item) =>
        h(
          "button",
          {
            key: item.path,
            className: route === item.path ? "nav-btn active" : "nav-btn",
            onClick: () => navigate(item.path),
          },
          item.label
        )
      )
    ),
    h("button", { className: "ghost-btn logout-btn", onClick: onLogout }, "退出登录")
  );
}

function Topbar({ route }) {
  const current = NAV_ITEMS.find((item) => item.path === route);
  return h(
    "header",
    { className: "topbar" },
    h("div", null, h("h2", null, current ? current.label : "商家后台"), h("p", null, "基于商品资料和店铺规则回答顾客咨询")),
    h("a", { href: "#/customer", className: "outline-link" }, "打开顾客端")
  );
}

function PageRouter({ route }) {
  switch (route) {
    case "/products":
      return h(ProductPage);
    case "/orders":
      return h(OrdersPage);
    case "/knowledge":
      return h(KnowledgePage);
    case "/test":
      return h(ChatPage, { customerMode: false });
    case "/aftersales":
      return h(AftersalesPage);
    case "/chat-records":
      return h(ChatRecordsPage);
    case "/missed":
      return h(MissedQuestionsPage);
    case "/customer":
      return h(CustomerPage);
    case "/dashboard":
    default:
      return h(Dashboard);
  }
}

function Dashboard() {
  const entries = [
    { label: "商品管理", path: "/products", desc: "导入商品 Excel / CSV，并写入向量知识库。" },
    { label: "订单管理", path: "/orders", desc: "查看本地模拟订单、物流状态和售后状态。" },
    { label: "知识库管理", path: "/knowledge", desc: "上传发货、退换货、售后、FAQ 等规则文件。" },
    { label: "AI 客服测试", path: "/test", desc: "模拟顾客问题，查看回答和命中来源。" },
    { label: "售后工单", path: "/aftersales", desc: "查看 AI 自动创建的退换货、退款、投诉工单。" },
    { label: "聊天记录", path: "/chat-records", desc: "查看顾客咨询、测试问答、mode 和人工处理状态。" },
    { label: "未命中问题", path: "/missed", desc: "收集知识库无法回答的问题，便于补充 FAQ。" },
    { label: "顾客端预览", path: "/customer", desc: "用聊天窗口体验真实咨询流程。" },
  ];
  return h(
    "section",
    { className: "dashboard-grid" },
    entries.map((entry) =>
      h(
        "article",
        { key: entry.path, className: "entry-card" },
        h("h3", null, entry.label),
        h("p", null, entry.desc),
        h("button", { className: "secondary-btn", onClick: () => navigate(entry.path) }, "进入")
      )
    )
  );
}

function ProductPage() {
  const [items, setItems] = useState([]);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const data = await apiRequest("/api/products");
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setStatus(err.message));
  }, []);

  async function upload(event) {
    event.preventDefault();
    if (!file) {
      setStatus("请选择商品 CSV 或 Excel 文件");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    setStatus("");
    try {
      const data = await apiRequest("/api/products/upload", { method: "POST", body: formData });
      setStatus(`已导入 ${data.saved_count} 个商品，写入 ${data.indexed_count} 条向量资料`);
      setFile(null);
      event.target.reset();
      await refresh();
    } catch (err) {
      setStatus(err.message);
    } finally {
      setLoading(false);
    }
  }

  return h(
    "section",
    { className: "content-stack" },
    h(
      "form",
      { className: "upload-band", onSubmit: upload },
      h("div", null, h("h3", null, "上传商品文件"), h("p", null, "支持 CSV、XLSX、XLS，商品名称为必填列")),
      h("input", {
        type: "file",
        accept: ".csv,.xlsx,.xls",
        onChange: (event) => setFile(event.target.files[0] || null),
      }),
      h("button", { className: "primary-btn", disabled: loading }, loading ? "上传中..." : "上传并入库")
    ),
    status && h("div", { className: status.includes("已导入") ? "notice success" : "notice" }, status),
    h(ProductTable, { items })
  );
}

function ProductTable({ items }) {
  return h(
    "section",
    { className: "table-section" },
    h("div", { className: "section-head" }, h("h3", null, "商品列表"), h("span", null, `${items.length} 条`)),
    h(
      "div",
      { className: "table-wrap" },
      h(
        "table",
        null,
        h(
          "thead",
          null,
          h(
            "tr",
            null,
            ["商品名称", "类目", "价格", "尺码", "材质", "适用人群", "卖点", "库存", "链接"].map((title) =>
              h("th", { key: title }, title)
            )
          )
        ),
        h(
          "tbody",
          null,
          items.length === 0
            ? h("tr", null, h("td", { colSpan: 9, className: "empty-cell" }, "暂无商品数据"))
            : items.map((item) =>
                h(
                  "tr",
                  { key: item.id },
                  h("td", null, item.name),
                  h("td", null, item.category || "-"),
                  h("td", null, item.price || "-"),
                  h("td", null, item.sizes || "-"),
                  h("td", null, item.material || "-"),
                  h("td", null, item.audience || "-"),
                  h("td", { className: "wide-cell" }, item.selling_points || "-"),
                  h("td", null, item.stock || "-"),
                  h(
                    "td",
                    null,
                    item.product_url
                      ? h("a", { href: item.product_url, target: "_blank", rel: "noreferrer" }, "查看")
                      : "-"
                  )
                )
              )
        )
      )
    )
  );
}

function OrdersPage() {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [expandedNo, setExpandedNo] = useState(null);
  const [status, setStatus] = useState("");

  async function refresh(nextKeyword = keyword) {
    const path = nextKeyword.trim() ? `/api/orders/search?keyword=${encodeURIComponent(nextKeyword.trim())}` : "/api/orders";
    const data = await apiRequest(path);
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setStatus(err.message));
  }, []);

  async function search(event) {
    event.preventDefault();
    setStatus("");
    setExpandedNo(null);
    try {
      await refresh(keyword);
    } catch (err) {
      setStatus(err.message);
    }
  }

  return h(
    "section",
    { className: "content-stack" },
    h(
      "form",
      { className: "toolbar-form", onSubmit: search },
      h("input", {
        value: keyword,
        placeholder: "按订单号、顾客昵称、商品、快递单号搜索",
        onChange: (event) => setKeyword(event.target.value),
      }),
      h("button", { className: "primary-btn" }, "搜索"),
      h("button", { type: "button", className: "secondary-btn", onClick: () => { setKeyword(""); refresh(""); } }, "重置")
    ),
    status && h("div", { className: "notice" }, status),
    h(
      "section",
      { className: "table-section" },
      h("div", { className: "section-head" }, h("h3", null, "订单列表"), h("span", null, `${items.length} 条`)),
      h(
        "div",
        { className: "table-wrap" },
        h(
          "table",
          null,
          h(
            "thead",
            null,
            h("tr", null, ["订单号", "顾客昵称", "商品名称", "订单状态", "物流状态", "快递单号", "售后状态", "下单时间", "操作"].map((title) => h("th", { key: title }, title)))
          ),
          h(
            "tbody",
            null,
            items.length === 0
              ? h("tr", null, h("td", { colSpan: 9, className: "empty-cell" }, "暂无订单"))
              : items.map((item) =>
                  h(
                    React.Fragment,
                    { key: item.order_no },
                    h(
                      "tr",
                      null,
                      h("td", null, item.order_no),
                      h("td", null, item.customer_name || "-"),
                      h("td", { className: "wide-cell" }, item.product_name || "-"),
                      h("td", null, h("span", { className: "status-badge" }, item.order_status || "-")),
                      h("td", null, h("span", { className: shippingBadgeClass(item.shipping_status) }, item.shipping_status || "-")),
                      h("td", null, item.tracking_no || "-"),
                      h("td", null, item.aftersale_status || "-"),
                      h("td", null, formatTime(item.created_at)),
                      h(
                        "td",
                        null,
                        h("button", { className: "secondary-btn small-btn", onClick: () => setExpandedNo(expandedNo === item.order_no ? null : item.order_no) }, expandedNo === item.order_no ? "收起" : "查看详情")
                      )
                    ),
                    expandedNo === item.order_no &&
                      h(
                        "tr",
                        null,
                        h(
                          "td",
                          { colSpan: 9, className: "detail-cell" },
                          h(OrderInfoCard, { order: item }),
                          h("div", { className: "meta-line" }, `发货时间：${formatTime(item.shipped_at)} · 支付金额：${formatMoney(item.paid_amount)}`)
                        )
                      )
                  )
                )
          )
        )
      )
    )
  );
}

function AftersalesPage() {
  const filters = [
    { key: "", label: "全部" },
    { key: "pending", label: "待处理" },
    { key: "processing", label: "处理中" },
    { key: "resolved", label: "已处理" },
    { key: "rejected", label: "已拒绝" },
  ];
  const statusOptions = ["pending", "processing", "resolved", "rejected"];
  const [filter, setFilter] = useState("");
  const [items, setItems] = useState([]);
  const [message, setMessage] = useState("");

  async function refresh(nextFilter = filter) {
    const path = nextFilter ? `/api/aftersales?status=${encodeURIComponent(nextFilter)}` : "/api/aftersales";
    const data = await apiRequest(path);
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setMessage(err.message));
  }, [filter]);

  async function updateStatus(id, nextStatus) {
    setMessage("");
    try {
      await apiRequest(`/api/aftersales/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      await refresh();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return h(
    "section",
    { className: "content-stack" },
    h(
      "div",
      { className: "filter-bar" },
      filters.map((item) =>
        h("button", { key: item.key || "all", className: filter === item.key ? "chip-btn active" : "chip-btn", onClick: () => setFilter(item.key) }, item.label)
      )
    ),
    message && h("div", { className: "notice" }, message),
    h(
      "section",
      { className: "table-section" },
      h("div", { className: "section-head" }, h("h3", null, "售后工单"), h("span", null, `${items.length} 条`)),
      h(
        "div",
        { className: "table-wrap" },
        h(
          "table",
          null,
          h("thead", null, h("tr", null, ["工单编号", "订单号", "问题类型", "问题描述", "AI 建议", "状态", "人工", "创建时间", "修改状态"].map((title) => h("th", { key: title }, title)))),
          h(
            "tbody",
            null,
            items.length === 0
              ? h("tr", null, h("td", { colSpan: 9, className: "empty-cell" }, "暂无售后工单"))
              : items.map((item) =>
                  h(
                    "tr",
                    { key: item.id },
                    h("td", null, item.ticket_no),
                    h("td", null, item.order_no || "-"),
                    h("td", null, item.issue_type),
                    h("td", { className: "wide-cell" }, summarizeText(item.issue_description, 72)),
                    h("td", { className: "wide-cell" }, summarizeText(item.ai_suggestion, 84)),
                    h("td", null, h("span", { className: ticketStatusClass(item.status) }, statusLabel(item.status))),
                    h("td", null, item.needs_human ? h("span", { className: "status-badge danger" }, "需要") : h("span", { className: "status-badge" }, "否")),
                    h("td", null, formatTime(item.created_at)),
                    h(
                      "td",
                      null,
                      h(
                        "div",
                        { className: "inline-actions" },
                        statusOptions.map((status) =>
                          h("button", { key: status, className: item.status === status ? "small-btn secondary-btn active-status" : "small-btn secondary-btn", onClick: () => updateStatus(item.id, status) }, statusLabel(status))
                        )
                      )
                    )
                  )
                )
          )
        )
      )
    )
  );
}

function KnowledgePage() {
  const [items, setItems] = useState([]);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const data = await apiRequest("/api/knowledge");
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setStatus(err.message));
  }, []);

  async function upload(event) {
    event.preventDefault();
    if (!file) {
      setStatus("请选择 TXT 或 Markdown 文件");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    setStatus("");
    try {
      const data = await apiRequest("/api/knowledge/upload", { method: "POST", body: formData });
      setStatus(`已上传 ${data.file.filename}，切分 ${data.file.chunk_count} 段，写入 ${data.indexed_count} 条向量资料`);
      setFile(null);
      event.target.reset();
      await refresh();
    } catch (err) {
      setStatus(err.message);
    } finally {
      setLoading(false);
    }
  }

  return h(
    "section",
    { className: "content-stack" },
    h(
      "form",
      { className: "upload-band", onSubmit: upload },
      h("div", null, h("h3", null, "上传知识文件"), h("p", null, "支持 TXT、MD，可放发货、退换货、售后、FAQ 等规则")),
      h("input", {
        type: "file",
        accept: ".txt,.md,.markdown",
        onChange: (event) => setFile(event.target.files[0] || null),
      }),
      h("button", { className: "primary-btn", disabled: loading }, loading ? "上传中..." : "上传并切分")
    ),
    status && h("div", { className: status.includes("已上传") ? "notice success" : "notice" }, status),
    h(
      "section",
      { className: "knowledge-list" },
      h("div", { className: "section-head" }, h("h3", null, "知识文件"), h("span", null, `${items.length} 个文件`)),
      items.length === 0
        ? h("div", { className: "empty-state" }, "暂无知识文件")
        : items.map((item) =>
            h(
              "article",
              { key: item.id, className: "knowledge-item" },
              h("div", null, h("h4", null, item.filename), h("p", null, item.preview || "-")),
              h("div", { className: "meta-line" }, `${item.chunk_count} 段`, " · ", formatTime(item.created_at))
            )
          )
    )
  );
}

function ChatRecordsPage() {
  const filters = [
    { key: "all", label: "全部" },
    { key: "human", label: "需要人工处理" },
    { key: "deepseek", label: "DeepSeek 成功" },
    { key: "fallback", label: "fallback" },
  ];
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [status, setStatus] = useState("");

  async function refresh(nextFilter = filter) {
    const data = await apiRequest(`/api/chat/records?filter=${encodeURIComponent(nextFilter)}`);
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setStatus(err.message));
  }, [filter]);

  function changeFilter(nextFilter) {
    setFilter(nextFilter);
    setExpandedId(null);
  }

  return h(
    "section",
    { className: "content-stack" },
    h(
      "div",
      { className: "filter-bar" },
      filters.map((item) =>
        h(
          "button",
          {
            key: item.key,
            className: filter === item.key ? "chip-btn active" : "chip-btn",
            onClick: () => changeFilter(item.key),
          },
          item.label
        )
      )
    ),
    status && h("div", { className: "notice" }, status),
    h(
      "section",
      { className: "table-section" },
      h("div", { className: "section-head" }, h("h3", null, "聊天记录"), h("span", null, `${items.length} 条`)),
      h(
        "div",
        { className: "table-wrap" },
        h(
          "table",
          null,
          h(
            "thead",
            null,
            h(
              "tr",
              null,
              ["用户问题", "AI 回答摘要", "人工处理", "mode", "创建时间", "操作"].map((title) => h("th", { key: title }, title))
            )
          ),
          h(
            "tbody",
            null,
            items.length === 0
              ? h("tr", null, h("td", { colSpan: 6, className: "empty-cell" }, "暂无聊天记录"))
              : items.map((item) =>
                  h(
                    React.Fragment,
                    { key: item.id },
                    h(
                      "tr",
                      null,
                      h("td", { className: "wide-cell" }, item.question),
                      h("td", { className: "wide-cell" }, summarizeText(item.answer, 88)),
                      h("td", null, item.needs_human ? h("span", { className: "status-badge danger" }, "需要") : h("span", { className: "status-badge" }, "否")),
                      h("td", null, h("code", { className: "mode-code" }, item.mode)),
                      h("td", null, formatTime(item.created_at)),
                      h(
                        "td",
                        null,
                        h(
                          "button",
                          { className: "secondary-btn small-btn", onClick: () => setExpandedId(expandedId === item.id ? null : item.id) },
                          expandedId === item.id ? "收起" : "查看详情"
                        )
                      )
                    ),
                    expandedId === item.id &&
                      h(
                        "tr",
                        null,
                        h(
                          "td",
                          { colSpan: 6, className: "detail-cell" },
                          h("strong", null, "完整回答"),
                          h("p", null, item.answer),
                          h("strong", null, "来源"),
                          h(RecordSourceList, { sourcesJson: item.sources_json }),
                          h(RecordExtraCards, { orderJson: item.order_card_json, ticketJson: item.aftersale_ticket_json }),
                          h("div", { className: "meta-line" }, `session_id: ${item.session_id} · user_type: ${item.user_type}`)
                        )
                      )
                  )
                )
          )
        )
      )
    )
  );
}

function RecordSourceList({ sourcesJson }) {
  let sources = [];
  try {
    sources = JSON.parse(sourcesJson || "[]");
  } catch (_) {
    sources = [];
  }
  if (sources.length === 0) {
    return h("p", { className: "muted-line" }, "无来源");
  }
  return h(
    "div",
    { className: "record-sources" },
    sources.slice(0, 3).map((source, index) => {
      const metadata = source.metadata || {};
      return h(
        "div",
        { key: index, className: "record-source-item" },
        h("span", null, metadata.source_type === "product" ? "商品" : "规则"),
        h("strong", null, metadata.title || "未知来源"),
        h("p", null, source.summary || "")
      );
    })
  );
}

function RecordExtraCards({ orderJson, ticketJson }) {
  let order = null;
  let ticket = null;
  try {
    order = orderJson ? JSON.parse(orderJson) : null;
  } catch (_) {
    order = null;
  }
  try {
    ticket = ticketJson ? JSON.parse(ticketJson) : null;
  } catch (_) {
    ticket = null;
  }
  if (!order && !ticket) return null;
  return h(
    "div",
    { className: "record-extra-cards" },
    order && h(OrderInfoCard, { order }),
    ticket && h(AftersaleTicketInfoCard, { ticket })
  );
}

function MissedQuestionsPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("");

  async function refresh() {
    const data = await apiRequest("/api/missed-questions");
    setItems(data.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setStatus(err.message));
  }, []);

  async function resolveItem(id) {
    setStatus("");
    try {
      await apiRequest(`/api/missed-questions/${id}/resolve`, { method: "PATCH" });
      await refresh();
    } catch (err) {
      setStatus(err.message);
    }
  }

  return h(
    "section",
    { className: "content-stack" },
    status && h("div", { className: "notice" }, status),
    h(
      "section",
      { className: "table-section" },
      h("div", { className: "section-head" }, h("h3", null, "未命中问题"), h("span", null, `${items.length} 条`)),
      h(
        "div",
        { className: "table-wrap" },
        h(
          "table",
          null,
          h("thead", null, h("tr", null, ["问题", "原因", "状态", "创建时间", "操作"].map((title) => h("th", { key: title }, title)))),
          h(
            "tbody",
            null,
            items.length === 0
              ? h("tr", null, h("td", { colSpan: 5, className: "empty-cell" }, "暂无未命中问题"))
              : items.map((item) =>
                  h(
                    "tr",
                    { key: item.id },
                    h("td", { className: "wide-cell" }, item.question),
                    h("td", null, item.reason),
                    h("td", null, h("span", { className: item.status === "pending" ? "status-badge warning" : "status-badge success" }, item.status === "pending" ? "待处理" : "已处理")),
                    h("td", null, formatTime(item.created_at)),
                    h(
                      "td",
                      null,
                      item.status === "pending"
                        ? h("button", { className: "secondary-btn small-btn", onClick: () => resolveItem(item.id) }, "标记已处理")
                        : "-"
                    )
                  )
                )
          )
        )
      )
    )
  );
}

function summarizeText(text, limit) {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact || "-";
  return compact.slice(0, limit - 3) + "...";
}

function formatMoney(value) {
  if (value === undefined || value === null || value === "") return "-";
  const text = String(value);
  return text.includes("¥") || text.includes("元") ? text : `¥${text}`;
}

function statusLabel(status) {
  const labels = {
    pending: "待处理",
    processing: "处理中",
    resolved: "已处理",
    rejected: "已拒绝",
  };
  return labels[status] || status || "-";
}

function ticketStatusClass(status) {
  if (status === "resolved") return "status-badge success";
  if (status === "rejected") return "status-badge danger";
  if (status === "processing") return "status-badge warning";
  return "status-badge";
}

function shippingBadgeClass(status) {
  if (status === "已签收") return "status-badge success";
  if (status === "运输中" || status === "已发货") return "status-badge warning";
  return "status-badge";
}

function OrderInfoCard({ order }) {
  if (!order) return null;
  return h(
    "article",
    { className: "order-card" },
    h(
      "div",
      { className: "order-card-head" },
      h("strong", null, `订单 ${order.order_no || "-"}`),
      h("span", { className: "status-badge" }, order.order_status || "-")
    ),
    h("div", { className: "order-grid" },
      h("span", null, "商品"), h("strong", null, order.product_name || "-"),
      h("span", null, "物流"), h("strong", null, order.shipping_status || "-"),
      h("span", null, "快递"), h("strong", null, order.express_company || "-"),
      h("span", null, "单号"), h("strong", null, order.tracking_no || "-"),
      h("span", null, "售后"), h("strong", null, order.aftersale_status || "-")
    )
  );
}

function AftersaleTicketInfoCard({ ticket }) {
  if (!ticket) return null;
  return h(
    "article",
    { className: "ticket-card" },
    h(
      "div",
      { className: "order-card-head" },
      h("strong", null, ticket.ticket_no || "售后工单"),
      h("span", { className: ticketStatusClass(ticket.status) }, statusLabel(ticket.status))
    ),
    h("div", { className: "order-grid" },
      h("span", null, "问题类型"), h("strong", null, ticket.issue_type || "-"),
      h("span", null, "订单号"), h("strong", null, ticket.order_no || "-"),
      h("span", null, "人工处理"), h("strong", null, ticket.needs_human ? "需要" : "否")
    )
  );
}

function ChatPage({ customerMode }) {
  return h(
    "section",
    { className: "content-stack" },
    h(
      "div",
      { className: "sample-strip" },
      SAMPLE_QUESTIONS.map((question) =>
        h("button", { key: question, className: "chip-btn", onClick: () => window.dispatchEvent(new CustomEvent("sample-question", { detail: question })) }, question)
      )
    ),
    h(ChatConsole, { customerMode })
  );
}

function CustomerPage() {
  return h(
    "section",
    { className: "customer-page" },
    h(
      "div",
      { className: "shop-header" },
      h(
        "div",
        { className: "shop-identity" },
        h("div", { className: "shop-avatar" }, "店"),
        h("div", null, h("strong", null, "示例小店客服"), h("span", null, "官方客服 · 在线"))
      ),
      h("a", { href: "#/dashboard", className: "shop-link" }, "商家后台")
    ),
    h(ChatConsole, { customerMode: true })
  );
}

function ChatConsole({ customerMode }) {
  const sessionId = useMemo(() => (customerMode ? getCustomerSessionId() : makeSessionId("merchant-test")), [customerMode]);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      answer: customerMode
        ? "您好，欢迎咨询。可以问我商品推荐、尺码、材质、发货、退换货或售后问题。"
        : "输入顾客问题后，我会展示回答、命中的知识来源和摘要。",
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    const handler = (event) => setInput(event.detail);
    window.addEventListener("sample-question", handler);
    return () => window.removeEventListener("sample-question", handler);
  }, []);

  useEffect(() => {
    bottomRef.current && bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function ask(question) {
    const text = question.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((current) => [...current, { role: "user", content: text }]);
    setLoading(true);
    try {
      const data = await apiRequest("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          top_k: 5,
          session_id: sessionId,
          user_type: customerMode ? "customer" : "merchant_test",
        }),
      });
      setMessages((current) => [...current, { role: "assistant", ...data }]);
    } catch (err) {
      setMessages((current) => [...current, { role: "assistant", answer: err.message, sources: [] }]);
    } finally {
      setLoading(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    ask(input);
  }

  return h(
    "div",
    { className: customerMode ? "chat-window customer-chat" : "chat-window" },
    h(
      "div",
      { className: "chat-messages" },
      messages.map((message, index) =>
        h(
          "div",
          { key: index, className: `message-row ${message.role}` },
          customerMode && message.role === "assistant" && h("div", { className: "chat-avatar agent" }, "服"),
          h(
            "div",
            { className: "bubble" },
            message.role === "user"
              ? message.content
              : h(
                  React.Fragment,
                  null,
                  !customerMode && message.question && h("div", { className: "question-line" }, `用户问题：${message.question}`),
                  !customerMode && message.mode && h("div", { className: "mode-line" }, `mode: ${message.mode}`),
                  message.needs_human && h("div", { className: customerMode ? "handoff-banner customer" : "handoff-banner" }, "已转人工处理"),
                  h("p", null, message.answer),
                  h(ProductCardList, { cards: message.product_cards || [], customerMode }),
                  h(OrderInfoCard, { order: message.order_card }),
                  h(AftersaleTicketInfoCard, { ticket: message.aftersale_ticket }),
                  !customerMode && h(SourceList, { sources: message.sources || [] })
                )
          ),
          customerMode && message.role === "user" && h("div", { className: "chat-avatar buyer" }, "我")
        )
      ),
      loading &&
        h(
          "div",
          { className: "message-row assistant" },
          customerMode && h("div", { className: "chat-avatar agent" }, "服"),
          h("div", { className: "bubble" }, customerMode ? "正在为您查询..." : "正在检索知识库并生成回答...")
        ),
      h("div", { ref: bottomRef })
    ),
    customerMode &&
      h(
        "div",
        { className: "customer-quick-bar" },
        ["订单 10001 发货了吗？", "可以退货吗？", "有 200 元以内的包推荐吗？", "我要找人工客服"].map((question) =>
          h("button", { key: question, type: "button", onClick: () => ask(question) }, question)
        )
      ),
    h(
      "form",
      { className: "chat-input-bar", onSubmit: submit },
      h("input", {
        value: input,
        placeholder: customerMode ? "咨询商品、尺码、发货、退换货..." : "输入测试问题",
        onChange: (event) => setInput(event.target.value),
      }),
      h("button", { className: "primary-btn", disabled: loading }, "发送")
    )
  );
}

function ProductCardList({ cards, customerMode }) {
  if (!cards || cards.length === 0) return null;
  return h(
    "div",
    { className: customerMode ? "product-cards customer" : "product-cards" },
    cards.slice(0, 3).map((card) =>
      h(
        "article",
        { key: card.id || card.name, className: "product-card" },
        h(
          "div",
          { className: "product-card-head" },
          h("strong", null, card.name || "未命名商品"),
          h("span", { className: "product-price" }, formatProductPrice(card.price))
        ),
        h("div", { className: "product-meta" }, card.category || "未标注类目"),
        card.target_user && h("div", { className: "product-audience" }, `适合：${card.target_user}`),
        card.selling_points && h("p", { className: "product-desc" }, summarizeText(card.selling_points, 54)),
        h("div", { className: "product-stock" }, `库存：${card.stock || "-"}`),
        card.link
          ? h("a", { className: "product-action", href: card.link, target: "_blank", rel: "noreferrer" }, "查看商品")
          : h("button", { className: "product-action disabled", disabled: true }, "暂无链接")
      )
    )
  );
}

function formatProductPrice(value) {
  if (value === undefined || value === null || value === "") return "价格待确认";
  const text = String(value);
  return text.includes("¥") || text.includes("元") ? text : `¥${text}`;
}

function SourceList({ sources }) {
  if (!sources || sources.length === 0) {
    return h("div", { className: "sources empty" }, "命中的知识来源：无");
  }
  return h(
    "div",
    { className: "sources" },
    h("strong", null, "命中的知识来源"),
    sources.map((source, index) => {
      const metadata = source.metadata || {};
      const typeLabel = metadata.source_type === "product" ? "商品资料" : "店铺规则";
      return h(
        "article",
        { key: `${metadata.source_type}-${metadata.source_id}-${index}`, className: "source-card" },
        h("div", { className: "source-title" }, h("span", null, typeLabel), h("strong", null, metadata.title || "未知来源")),
        h("p", null, source.summary || source.content)
      );
    })
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
