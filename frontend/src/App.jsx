import { useState } from "react";

const projects = [
  { name: "Guitar Livre", icon: "guitar", active: true },
  { name: "Mosaic", icon: "cube" },
  { name: "AlugaCar", icon: "car" },
];

const conversations = {
  Hoje: ["Arquitetura do projeto", "Estrutura do banco de dados", "Ideias de funcionalidades"],
  Ontem: ["Onde paramos?", "Análise de requisitos", "Plano de desenvolvimento"],
  "Últimos 7 dias": ["Modelo de negócio", "Estratégia de lançamento", "Público alvo"],
};

const memories = [
  {
    title: "Stack preferida",
    text: "Você costuma usar Next.js em seus projetos web.",
    date: "Hoje",
  },
  {
    title: "Objetivo do projeto",
    text: "Plataforma de ensino de música online com foco em iniciantes.",
    date: "Ontem",
  },
  {
    title: "Público alvo",
    text: "Iniciantes e intermediários, 18–35 anos, Brasil.",
    date: "2 dias",
  },
];

const related = ["Análise de requisitos", "Plano de desenvolvimento", "Modelo de negócio"];

function Icon({ name, size = 18 }) {
  const paths = {
    home: <><path d="m3 9 9-7 9 7" /><path d="M5 10v10h14V10" /><path d="M9 20v-6h6v6" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 5 5" /></>,
    settings: <><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /><circle cx="12" cy="12" r="4" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.4 2.4 0 1 1 4.1 1.7c-.9.9-1.9 1.3-1.9 2.8M12 17h.01" /></>,
    file: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v5h5" /></>,
    folder: <><path d="M3 6h7l2 2h9v10H3z" /></>,
    check: <><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.3 2.3 4.7-5" /></>,
    memory: <><path d="M5 5h14v14H5z" /><path d="M8 9h8M8 13h6M8 17h4" /></>,
    tool: <><path d="m14.5 6.5 3-3 3 3-3 3" /><path d="M17.5 6.5 11 13l-3 3-4 1 1-4 3-3 6.5-6.5" /></>,
    note: <><path d="M5 3h11l3 3v15H5z" /><path d="M16 3v4h4M8 11h8M8 15h8M8 7h3" /></>,
    paperclip: <><path d="m9 12 5.5-5.5a3 3 0 0 1 4.2 4.2L11 18.4a5 5 0 0 1-7.1-7.1l7.1-7.1" /></>,
    globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21z" /><path d="M4 5.5v15M8 7h8M8 11h7" /></>,
    at: <><circle cx="12" cy="12" r="4" /><path d="M16 12v1a2 2 0 0 0 4 0v-1a8 8 0 1 0-2.3 5.7" /></>,
    send: <><path d="m4 4 16 8-16 8 3-8z" /><path d="M7 12h13" /></>,
    chevron: <path d="m8 10 4 4 4-4" />,
    external: <><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 13v6H5V6h6" /></>,
    box: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z" /><path d="m4 7.5 8 4.5 8-4.5M12 12v9" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5" /></>,
    history: <><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" /><path d="M4 4v4.5h4.5M12 7v5l3 2" /></>,
    cube: <><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z" /><path d="m4 7.5 8 4.5 8-4.5M12 12v9" /></>,
    guitar: <><path d="M14.5 5.5 18 2l1 1-3.5 3.5" /><path d="m14 7 3 3" /><path d="M15.5 9.5c1.3 1.3 1.2 3.4-.1 4.7l-2.1 2.1a3.4 3.4 0 0 1-4.8-4.8l2.1-2.1c1.3-1.3 3.4-1.4 4.7-.1z" /><path d="m9 15-4 4" /></>,
    car: <><path d="M5 16h14l-1-6H6z" /><path d="M3 16h2v3h2v-3h10v3h2v-3h2" /><circle cx="7.5" cy="16" r="1" /><circle cx="16.5" cy="16" r="1" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.box}
    </svg>
  );
}

function MosaicMark({ compact = false }) {
  return (
    <div className={compact ? "mosaic-mark compact" : "mosaic-mark"} aria-hidden="true">
      <svg viewBox="0 0 80 80" fill="none">
        <path d="M40 4 68 20v32L40 68 12 52V20z" stroke="currentColor" strokeWidth="2" />
        <path d="m40 4 14 8v16L40 36 26 28V12z" fill="currentColor" opacity=".82" />
        <path d="m26 28 14 8v16l-14 8-14-8V36z" fill="currentColor" opacity=".45" />
        <path d="m54 28 14-8v32l-14 8z" fill="currentColor" opacity=".25" />
        <path d="m40 36 14-8v16l-14 8z" fill="currentColor" opacity=".9" />
        <path d="m40 52 14 8-14 8z" fill="currentColor" opacity=".45" />
      </svg>
    </div>
  );
}

function ProjectIcon({ type }) {
  return <span className="project-icon"><Icon name={type} size={18} /></span>;
}

function Sidebar({ mobileOpen, onClose }) {
  return (
    <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
      <div className="brand-row">
        <MosaicMark />
        <span className="wordmark">MOSAIC</span>
        <button className="mobile-close" onClick={onClose}>×</button>
      </div>

      <button className="new-chat">
        <Icon name="plus" size={19} />
        <span>Nova conversa</span>
      </button>

      <nav className="side-primary">
        <button><Icon name="home" /><span>Início</span></button>
        <div className="section-heading"><span>Projetos</span><Icon name="plus" size={16} /></div>

        {projects.map((project) => (
          <button key={project.name} className={project.active ? "side-project active" : "side-project"}>
            <ProjectIcon type={project.icon} />
            <span>{project.name}</span>
          </button>
        ))}

        <button className="new-project"><Icon name="plus" size={17} /><span>Novo projeto</span></button>
      </nav>

      <div className="conversation-nav">
        <div className="section-heading">
          <span>Conversas</span>
          <Icon name="search" size={17} />
        </div>
        {Object.entries(conversations).map(([group, items]) => (
          <div className="conversation-group" key={group}>
            <span className="group-label">{group}</span>
            {items.map((item, index) => (
              <button className={index === 0 && group === "Hoje" ? "conversation-item selected" : "conversation-item"} key={item}>
                <span className="tiny-chevron">›</span>
                <span>{item}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      <div className="side-bottom">
        <button><Icon name="settings" /><span>Configurações</span></button>
        <button><Icon name="help" /><span>Ajuda</span></button>
      </div>
    </aside>
  );
}

function TopBar({ onMenu, model, setModel }) {
  const [open, setOpen] = useState(false);
  const models = ["Qwen 3B", "Llama"];

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu}><Icon name="menu" /></button>
      <button className="workspace-file"><Icon name="file" /></button>
      <div className="top-project">
        <span className="top-project-icon"><ProjectIcon type="guitar" /></span>
        <div>
          <strong>Guitar Livre</strong>
          <small>Development Project</small>
        </div>
        <Icon name="chevron" size={15} />
      </div>

      <div className="top-actions">
        <div className="model-picker">
          <button className="model-button" onClick={() => setOpen(!open)}>
            <span className="status-dot" />
            <span>{model}</span>
            <Icon name="chevron" size={15} />
          </button>
          {open && (
            <div className="model-menu">
              {models.map((item) => (
                <button key={item} onClick={() => { setModel(item); setOpen(false); }}>
                  <span className={item === model ? "status-dot" : "status-dot muted"} />
                  {item}
                </button>
              ))}
            </div>
          )}
        </div>
        <span className="top-divider" />
        <button className="top-link"><Icon name="layers" size={16} />Contexto</button>
        <button className="top-link"><Icon name="memory" size={16} />Memória</button>
        <button className="top-link"><Icon name="tool" size={16} />Ferramentas</button>
        <span className="avatar">JD</span>
      </div>
    </header>
  );
}

function ProjectHeader({ activeTab, setActiveTab }) {
  const tabs = [
    ["note", "Conversa"],
    ["folder", "Arquivos"],
    ["check", "Tarefas"],
    ["memory", "Memória"],
    ["tool", "Artefatos"],
    ["note", "Notas"],
  ];

  return (
    <section className="project-header">
      <div className="project-identity">
        <MosaicMark compact />
        <div>
          <h1>Guitar Livre</h1>
          <p>Desenvolvimento de uma plataforma de ensino de música online.</p>
        </div>
      </div>
      <nav className="project-tabs">
        {tabs.map(([icon, label]) => (
          <button key={label} className={activeTab === label ? "active" : ""} onClick={() => setActiveTab(label)}>
            <Icon name={icon} size={16} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </section>
  );
}

function ArchitectureCard() {
  return (
    <div className="architecture-card">
      <div className="architecture-title"><Icon name="layers" size={15} />Arquitetura (visão geral)</div>
      <div className="architecture-flow">
        <div className="flow-node"><Icon name="home" size={20} /><span>Cliente</span><small>Web / Mobile</small></div>
        <span className="flow-arrow">→</span>
        <div className="flow-node"><span className="react-glyph">⚛</span><span>Frontend</span><small>Next.js</small></div>
        <span className="flow-arrow">→</span>
        <div className="flow-node"><span className="node-glyph">JS</span><span>Backend</span><small>Node.js</small></div>
        <div className="flow-branches">
          <div><span>◉</span><span>Banco de Dados</span><small>PostgreSQL</small></div>
          <div><span>◌</span><span>Armazenamento</span><small>S3 / R2</small></div>
          <div><span>⚙</span><span>Serviços Externos</span><small>Pagamentos, Email, etc.</small></div>
        </div>
      </div>
    </div>
  );
}

function ChatContent() {
  return (
    <div className="chat-content">
      <div className="message user-message">
        <span className="message-avatar user">JD</span>
        <div className="message-bubble">
          <p>Quero estruturar a arquitetura do projeto.</p>
          <p>Podemos me ajudar a definir a stack, arquitetura e principais módulos?</p>
          <time>10:24</time>
        </div>
      </div>

      <div className="message assistant-message">
        <span className="message-avatar mosaic"><MosaicMark compact /></span>
        <div className="assistant-copy">
          <p>Claro! Vou te ajudar a estruturar a arquitetura do <strong>Guitar Livre</strong>.</p>
          <p>Com base nas conversas anteriores e nas informações do projeto, aqui está uma proposta inicial de arquitetura, stack e principais módulos.</p>
          <div className="message-rule" />
          <h2>1. Visão Geral da Arquitetura</h2>
          <p>O Guitar Livre pode ser estruturado como uma aplicação web moderna, com arquitetura modular, escalável e preparada para crescer.</p>
          <ArchitectureCard />
          <h2>2. Stack Sugerida</h2>
          <div className="stack-table">
            <div className="table-row table-head"><span>Camada</span><span>Tecnologia</span><span>Justificativa</span></div>
            <div className="table-row"><span>◈ Frontend</span><span>Next.js (React)</span><span>Performance, SEO, ecossistema robusto</span></div>
            <div className="table-row"><span>◆ Backend</span><span>Node.js</span><span>Flexibilidade e velocidade de desenvolvimento</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Composer({ model }) {
  const [text, setText] = useState("");

  function submit(event) {
    event.preventDefault();
    if (!text.trim()) return;
    setText("");
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Digite sua mensagem..."
        rows="2"
        aria-label="Mensagem"
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit(event);
          }
        }}
      />
      <div className="composer-toolbar">
        <div className="composer-tools">
          <button type="button" aria-label="Adicionar"><Icon name="plus" /></button>
          <button type="button" aria-label="Pesquisa web"><Icon name="globe" /></button>
          <button type="button" aria-label="Arquivos"><Icon name="book" /></button>
          <button type="button" aria-label="Menções"><Icon name="at" /></button>
        </div>
        <div className="composer-submit">
          <button className="composer-model" type="button">
            <span className="status-dot" />{model}<Icon name="chevron" size={14} />
          </button>
          <button className="send-button" type="submit" aria-label="Enviar"><Icon name="send" size={19} /></button>
        </div>
      </div>
    </form>
  );
}

function ContextPanel({ tab, setTab, model }) {
  const tabs = ["Contexto", "Memória", "Arquivos"];

  return (
    <aside className="context-panel">
      <nav className="context-tabs">
        {tabs.map((item) => (
          <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item}</button>
        ))}
      </nav>

      {tab === "Contexto" && (
        <>
          <section className="context-card">
            <div className="card-heading"><strong>Contexto atual</strong><span>O que o Mosaic está usando para responder</span></div>
            <ContextRow icon="cube" label="Projeto"><strong>Guitar Livre</strong><small>Development Project</small></ContextRow>
            <ContextRow icon="box" label="Modelo"><strong>{model}</strong><span className="online"><i />Online</span></ContextRow>
            <ContextRow icon="layers" label="Memória"><strong>3 itens relevantes</strong><small>Do projeto</small></ContextRow>
            <ContextRow icon="history" label="Histórico"><strong>12 mensagens</strong><small>Nesta conversa</small></ContextRow>
            <ContextRow icon="file" label="Arquivos"><strong>2 arquivos</strong><small>No projeto</small></ContextRow>
            <ContextRow icon="tool" label="Ferramentas"><span className="muted-copy">Nenhuma ferramenta ativa</span></ContextRow>
          </section>

          <section className="side-card">
            <div className="side-card-heading"><strong>Memórias relevantes</strong><button>Ver todas</button></div>
            {memories.map((memory) => (
              <div className="memory-item" key={memory.title}>
                <span className="memory-icon"><Icon name="note" size={16} /></span>
                <div><div className="memory-meta"><strong>{memory.title}</strong><span>{memory.date}</span></div><p>{memory.text}</p></div>
              </div>
            ))}
          </section>

          <section className="side-card related-card">
            <div className="side-card-heading"><strong>Conversas relacionadas</strong><button>Ver todas</button></div>
            {related.map((item) => <button className="related-item" key={item}><Icon name="note" size={15} />{item}</button>)}
          </section>
        </>
      )}

      {tab === "Memória" && (
        <section className="context-card standalone-card">
          <div className="card-heading"><strong>Memória</strong><span>Informações relevantes associadas ao projeto</span></div>
          {memories.map((memory) => <div className="memory-item full" key={memory.title}><span className="memory-icon"><Icon name="memory" size={16} /></span><div><div className="memory-meta"><strong>{memory.title}</strong><span>{memory.date}</span></div><p>{memory.text}</p></div></div>)}
        </section>
      )}

      {tab === "Arquivos" && (
        <section className="context-card standalone-card">
          <div className="card-heading"><strong>Arquivos</strong><span>Arquivos disponíveis no projeto</span></div>
          <div className="empty-state"><Icon name="folder" size={24} /><strong>Arquivos do projeto</strong><span>Nenhuma integração de arquivos está ativa nesta etapa.</span></div>
        </section>
      )}
    </aside>
  );
}

function ContextRow({ icon, label, children }) {
  return (
    <div className="context-row">
      <span className="context-row-icon"><Icon name={icon} size={18} /></span>
      <span className="context-row-label">{label}</span>
      <div className="context-row-value">{children}</div>
    </div>
  );
}

function App() {
  const [mobileSidebar, setMobileSidebar] = useState(false);
  const [contextTab, setContextTab] = useState("Contexto");
  const [projectTab, setProjectTab] = useState("Conversa");
  const [model, setModel] = useState("Qwen 3B");

  return (
    <div className="app-shell">
      <Sidebar mobileOpen={mobileSidebar} onClose={() => setMobileSidebar(false)} />
      {mobileSidebar && <button className="mobile-overlay" aria-label="Fechar menu" onClick={() => setMobileSidebar(false)} />}
      <div className="app-main">
        <TopBar onMenu={() => setMobileSidebar(true)} model={model} setModel={setModel} />
        <div className="workspace-grid">
          <main className="workspace">
            <ProjectHeader activeTab={projectTab} setActiveTab={setProjectTab} />
            <div className="chat-scroll">
              <ChatContent />
            </div>
            <Composer model={model} />
          </main>
          <ContextPanel tab={contextTab} setTab={setContextTab} model={model} />
        </div>
      </div>
    </div>
  );
}

export default App;
