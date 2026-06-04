const h = React.createElement;
const { useEffect, useMemo, useRef, useState } = React;

const NAV_ITEMS = [
  { path: "/dashboard", label: "后台首页" },
  { path: "/products", label: "商品管理" },
  { path: "/knowledge", label: "知识库管理" },
  { path: "/test", label: "AI 客服测试" },
  { path: "/customer", label: "顾客端预览" },
];

const SAMPLE_QUESTIONS = [
  "这件防晒衬衫适合夏天通勤穿吗？",
  "多久发货？",
  "可以退货吗？",
  "这款适合学生党吗？",
  "有 200 元以内的包推荐吗？",
  "质量问题怎么处理？",
];

function routeFromHash() {
  const route = window.location.hash.replace(/^#/, "");
  return route || "/dashboard";
}

function navigate(path) {
  window.location.hash = path;
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
    case "/knowledge":
      return h(KnowledgePage);
    case "/test":
      return h(ChatPage, { customerMode: false });
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
    { label: "知识库管理", path: "/knowledge", desc: "上传发货、退换货、售后、FAQ 等规则文件。" },
    { label: "AI 客服测试", path: "/test", desc: "模拟顾客问题，查看回答和命中来源。" },
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
        body: JSON.stringify({ question: text, top_k: 5 }),
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
                  h("p", null, message.answer),
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
        ["多久发货？", "可以退货吗？", "有适合学生党的商品吗？"].map((question) =>
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
