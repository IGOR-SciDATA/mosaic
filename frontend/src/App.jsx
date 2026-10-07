import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "./api";

function Icon({ name, size = 18 }) {
  const paths = {
    home:<><path d="m3 9 9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></>,
    plus:<><path d="M12 5v14M5 12h14"/></>,
    search:<><circle cx="11" cy="11" r="6.5"/><path d="m16 16 5 5"/></>,
    settings:<><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4-1.4"/></>,
    help:<><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.4 2.4 0 1 1 4.1 1.7c-.9.9-1.9 1.3-1.9 2.8M12 17h.01"/></>,
    file:<><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5"/></>,
    folder:<path d="M3 6h7l2 2h9v10H3z"/>,
    check:<><circle cx="12" cy="12" r="8.5"/><path d="m8.5 12 2.3 2.3 4.7-5"/></>,
    memory:<><path d="M5 5h14v14H5z"/><path d="M8 9h8M8 13h6M8 17h4"/></>,
    tool:<><path d="m14.5 6.5 3-3 3 3-3 3"/><path d="M17.5 6.5 11 13l-3 3-4 1 1-4 3-3 6.5-6.5"/></>,
    note:<><path d="M5 3h11l3 3v15H5z"/><path d="M16 3v4h4M8 11h8M8 15h8"/></>,
    globe:<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18"/></>,
    book:<><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21z"/><path d="M4 5.5v15M8 7h8M8 11h7"/></>,
    at:<><circle cx="12" cy="12" r="4"/><path d="M16 12v1a2 2 0 0 0 4 0v-1a8 8 0 1 0-2.3 5.7"/></>,
    send:<><path d="m4 4 16 8-16 8 3-8z"/><path d="M7 12h13"/></>,
    chevron:<path d="m8 10 4 4 4-4"/>,
    box:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
    layers:<><path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/></>,
    history:<><path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5"/><path d="M4 4v4.5h4.5M12 7v5l3 2"/></>,
    cube:<><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></>,
    guitar:<><path d="M14.5 5.5 18 2l1 1-3.5 3.5"/><path d="m14 7 3 3"/><path d="M15.5 9.5c1.3 1.3 1.2 3.4-.1 4.7l-2.1 2.1a3.4 3.4 0 0 1-4.8-4.8l2.1-2.1c1.3-1.3 3.4-1.4 4.7-.1z"/><path d="m9 15-4 4"/></>,
    car:<><path d="M5 16h14l-1-6H6z"/><path d="M3 16h2v3h2v-3h10v3h2v-3h2"/><circle cx="7.5" cy="16" r="1"/><circle cx="16.5" cy="16" r="1"/></>,
    menu:<><path d="M4 7h16M4 12h16M4 17h16"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.box}</svg>;
}

function MosaicMark({ compact=false }) {
  return <div className={compact ? "mosaic-mark compact" : "mosaic-mark"} aria-hidden="true"><svg viewBox="0 0 80 80" fill="none"><path d="M40 4 68 20v32L40 68 12 52V20z" stroke="currentColor" strokeWidth="2"/><path d="m40 4 14 8v16L40 36 26 28V12z" fill="currentColor" opacity=".82"/><path d="m26 28 14 8v16l-14 8-14-8V36z" fill="currentColor" opacity=".45"/><path d="m54 28 14-8v32l-14 8z" fill="currentColor" opacity=".25"/><path d="m40 36 14-8v16l-14 8z" fill="currentColor" opacity=".9"/></svg></div>;
}
const iconType = n => /guitar/i.test(n || "") ? "guitar" : /car/i.test(n || "") ? "car" : "cube";
const slugify = v => v.toLowerCase().trim().replace(/[^a-z0-9]+/gi,"-").replace(/^-|-$/g,"") || "project";
const groupFor = d => { const n=d ? Math.floor((Date.now()-new Date(d).getTime())/86400000) : 0; return n<1?"Hoje":n<2?"Ontem":"Últimos 7 dias"; };

function Sidebar({ projects, conversations, activeProjectId, activeConversationId, onProject, onConversation, onNewProject, onNewConversation, onModelSettings, onHelp, mobileOpen, onClose }) {
  const groups = useMemo(() => { const g={Hoje:[],Ontem:[],"Últimos 7 dias":[]}; conversations.forEach(c=>g[groupFor(c.updated_at)].push(c)); return g; },[conversations]);
  return <aside className={mobileOpen ? "sidebar open" : "sidebar"}>
    <div className="brand-row"><MosaicMark/><span className="wordmark">MOSAIC</span><button className="mobile-close" onClick={onClose}>×</button></div>
    <button className="new-chat" onClick={onNewConversation}><Icon name="plus" size={19}/>Nova conversa</button>
    <nav className="side-primary"><button><Icon name="home"/>Início</button>
      <div className="section-heading"><span>Projetos</span><button className="icon-inline" onClick={onNewProject}><Icon name="plus" size={16}/></button></div>
      {projects.map(p=><button key={p.id} onClick={()=>onProject(p.id)} className={p.id===activeProjectId?"side-project active":"side-project"}><span className="project-icon"><Icon name={iconType(p.name)} size={18}/></span><span>{p.name}</span></button>)}
      <button className="new-project" onClick={onNewProject}><Icon name="plus" size={17}/>Novo projeto</button>
    </nav>
    <div className="conversation-nav"><div className="section-heading"><span>Conversas</span><Icon name="search" size={17}/></div>
      {Object.entries(groups).map(([group,items])=><div className="conversation-group" key={group}><span className="group-label">{group}</span>{items.map(c=><button key={c.id} onClick={()=>onConversation(c.id)} className={c.id===activeConversationId?"conversation-item selected":"conversation-item"}><span className="tiny-chevron">›</span><span>{c.title}</span></button>)}</div>)}
      {!conversations.length&&<span className="sidebar-empty">Nenhuma conversa neste projeto.</span>}
    </div>
    <div className="side-bottom"><button onClick={onModelSettings}><Icon name="settings"/>Configurações</button><button onClick={onHelp}><Icon name="help"/>Ajuda</button></div>
  </aside>;
}

function TopBar({ onMenu, project, conversation, models, onModelChange, modelStatus, onModelSettings, onContext }) {
  const selectedModel=models.find(m=>m.id===conversation?.model_id);
  const running=selectedModel?.provider === "ollama" && modelStatus.running_models.includes(selectedModel.model_name);
  const statusLabel=!selectedModel ? "Nenhum modelo" : !modelStatus.online ? "Offline" : running ? "Rodando" : "Disponível";
  const statusClass=!selectedModel ? "offline" : !modelStatus.online ? "offline" : running ? "running" : "online";
  return <header className="topbar"><button className="mobile-menu" onClick={onMenu}><Icon name="menu"/></button><button className="workspace-file"><Icon name="file"/></button>
    <div className="top-project"><span className="top-project-icon"><span className="project-icon"><Icon name={iconType(project?.name)} size={18}/></span></span><div><strong>{project?.name || "Mosaic"}</strong><small>Development Project</small></div><Icon name="chevron" size={15}/></div>
    <div className="top-actions"><div className="model-picker"><select className="model-select" value={conversation?.model_id ?? ""} disabled={!conversation || !models.length} onChange={e=>onModelChange(Number(e.target.value))}><option value="">{conversation ? (models.length ? "Selecionar modelo" : "Nenhum modelo") : "Nenhuma conversa"}</option>{models.filter(m=>m.enabled || m.id===conversation?.model_id).map(m=><option key={m.id} value={m.id} disabled={!m.enabled}>{m.name}</option>)}</select><span className="model-provider">{selectedModel?.provider || ""}</span><span className={"model-status "+statusClass}><i/>{statusLabel}</span><button className="model-config-button" onClick={onModelSettings} disabled={!selectedModel}>Configurar</button></div><span className="top-divider"/><button className="top-link" onClick={()=>onContext("Contexto")}><Icon name="layers" size={16}/>Contexto</button><button className="top-link" onClick={()=>onContext("Memória")}><Icon name="memory" size={16}/>Memória</button><button className="top-link" onClick={()=>onContext("Arquivos")}><Icon name="tool" size={16}/>Ferramentas</button><span className="avatar">JD</span></div>
  </header>;
}

function ProjectHeader({ project, tab, setTab }) {
  const tabs=[["note","Conversa"],["folder","Arquivos"],["check","Tarefas"],["memory","Memória"],["tool","Artefatos"],["note","Notas"]];
  return <section className="project-header"><div className="project-identity"><MosaicMark compact/><div><h1>{project?.name || "Mosaic"}</h1><p>{project?.description || "Workspace de desenvolvimento do Mosaic."}</p></div></div><nav className="project-tabs">{tabs.map(([i,l])=><button key={l} className={tab===l?"active":""} onClick={()=>setTab(l)}><Icon name={i} size={16}/><span>{l}</span></button>)}</nav></section>;
}

function MessageList({ messages, streaming }) {
  if (!messages.length && !streaming) {
    return <div className="conversation-empty"><MosaicMark compact/><h2>Conversa pronta</h2><p>Envie uma mensagem para começar a conversar com o modelo selecionado.</p></div>;
  }

  return <div className="chat-content">
    {messages.map(message => message.role === "user"
      ? <div className="message user-message" key={message.id || message.localId}>
          <div className="message-bubble"><p>{message.content}</p><time>{new Date(message.created_at || Date.now()).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}</time></div>
          <div className="message-avatar user">JD</div>
        </div>
      : <div className="message assistant-message" key={message.id || message.localId}>
          <div className="message-avatar mosaic"><MosaicMark compact/></div>
          <div className="assistant-copy"><p>{message.content || (streaming ? "..." : "")}</p>{message.content&&<time className="message-time">{new Date(message.created_at || Date.now()).toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})}</time>}</div>
        </div>
    )}
  </div>;
}

function Composer({ disabled, onSubmit, model }) {
  const [text,setText]=useState("");
  const submit=e=>{e.preventDefault();if(!text.trim()||disabled)return;onSubmit(text.trim());setText("");};
  return <form className="composer" onSubmit={submit}><textarea disabled={disabled} value={text} onChange={e=>setText(e.target.value)} placeholder={disabled?"Selecione uma conversa para começar...":"Digite sua mensagem..."} rows="2" onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit(e);}}}/><div className="composer-toolbar"><div className="composer-tools"><button type="button" disabled={disabled}><Icon name="plus"/></button><button type="button" disabled={disabled}><Icon name="globe"/></button><button type="button" disabled={disabled}><Icon name="book"/></button><button type="button" disabled={disabled}><Icon name="at"/></button></div><div className="composer-submit"><span className="composer-model">{model?.name || "Modelo"}</span><button className="send-button" type="submit" disabled={disabled}><Icon name="send" size={19}/></button></div></div></form>;
}

function ContextRow({icon,label,children}){return <div className="context-row"><span className="context-row-icon"><Icon name={icon} size={18}/></span><span className="context-row-label">{label}</span><div className="context-row-value">{children}</div></div>;}
function ContextPanel({tab,setTab,project,conversation,model,memoryCount,messageCount,memories}) {
  return <aside className="context-panel"><nav className="context-tabs">{["Contexto","Memória","Arquivos"].map(x=><button key={x} className={tab===x?"active":""} onClick={()=>setTab(x)}>{x}</button>)}</nav>
    {tab==="Contexto"&&<><section className="context-card"><div className="card-heading"><strong>Contexto atual</strong><span>O que o Mosaic está usando para responder</span></div>
      <ContextRow icon="cube" label="Projeto">{project?<><strong>{project.name}</strong><small>{project.description || "Development Project"}</small></>:<span className="muted-copy">Nenhum projeto</span>}</ContextRow>
      <ContextRow icon="box" label="Modelo">{model?<><strong>{model.name}</strong><small>{model.provider} · {model.model_name}</small><span className="online"><i/>{model.enabled ? "Disponível" : "Desabilitado"}</span></>:<span className="muted-copy">Nenhum modelo selecionado</span>}</ContextRow>
      <ContextRow icon="layers" label="Memória"><strong>{memoryCount} {memoryCount === 1 ? "item" : "itens"} relevantes</strong><small>Memórias do projeto</small></ContextRow>
      <ContextRow icon="history" label="Histórico"><strong>{messageCount} {messageCount === 1 ? "mensagem" : "mensagens"}</strong><small>Histórico da conversa</small></ContextRow>
      <ContextRow icon="file" label="Arquivos"><span className="muted-copy">Não disponível no Core atual</span></ContextRow>
      <ContextRow icon="tool" label="Ferramentas"><span className="muted-copy">Nenhuma ferramenta ativa</span></ContextRow>
    </section><section className="side-card"><div className="side-card-heading"><strong>Estado real</strong></div><div className="state-line">Projeto <b>{project?.id ?? "—"}</b></div><div className="state-line">Conversa <b>{conversation?.id ?? "—"}</b></div></section></>}
    {tab==="Memória"&&<section className="context-card standalone-card"><div className="card-heading"><strong>Memória</strong><span>{memoryCount} {memoryCount === 1 ? "item" : "itens"} do projeto</span></div>{memoryCount?<div className="memory-list">{memories.map(memory=><div className="memory-item" key={memory.id}><div className="memory-item-head"><strong>{memory.key}</strong><span className="memory-type">{memory.type}</span></div><span>{memory.value}</span><small>Origem: {memory.source}{memory.confidence !== null && memory.confidence !== undefined ? ` · Confiança: ${Math.round(memory.confidence * 100)}%` : ""}</small></div>)}</div>:<div className="empty-state"><Icon name="memory" size={24}/><strong>Nenhuma memória</strong><span>O projeto ainda não possui memórias persistidas.</span></div>}</section>}
    {tab==="Arquivos"&&<section className="context-card standalone-card"><div className="card-heading"><strong>Arquivos</strong><span>Arquivos do projeto.</span></div><div className="empty-state"><Icon name="folder" size={24}/><strong>Arquivos</strong><span>Integração de arquivos ainda não faz parte desta fase.</span></div></section>}
  </aside>;
}

function Modal({title,onClose,children}){
  if(typeof document === "undefined") return null;
  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={e=>e.stopPropagation()}>
        <div className="modal-header"><strong>{title}</strong><button type="button" onClick={onClose} aria-label="Fechar">×</button></div>
        {children}
      </div>
    </div>,
    document.body
  );
}


export default function App(){
  const [projects,setProjects]=useState([]),[conversations,setConversations]=useState([]),[models,setModels]=useState([]),[memories,setMemories]=useState([]),[projectId,setProjectId]=useState(null),[conversationId,setConversationId]=useState(null),[messages,setMessages]=useState([]);
  const [mobile,setMobile]=useState(false),[contextTab,setContextTab]=useState("Contexto"),[projectTab,setProjectTab]=useState("Conversa"),[loading,setLoading]=useState(true),[messagesLoading,setMessagesLoading]=useState(false),[sending,setSending]=useState(false),[error,setError]=useState(""),[modal,setModal]=useState(null),[saving,setSaving]=useState(false),[modelStatus,setModelStatus]=useState({provider:"ollama",online:false,running_models:[]});
  const project=projects.find(p=>p.id===projectId)||null,conversation=conversations.find(c=>c.id===conversationId)||null,model=models.find(m=>m.id===conversation?.model_id)||null,projectConversations=conversations.filter(c=>c.project_id===projectId);

  async function load(){setLoading(true);setError("");try{const [ps,cs,ms]=await Promise.all([api.projects.list(),api.conversations.list(),api.models.list()]);setProjects(ps);setConversations(cs);setModels(ms);const savedP=Number(localStorage.getItem("mosaic.activeProjectId"));const p=ps.find(x=>x.id===savedP)||ps[0];const savedC=Number(localStorage.getItem("mosaic.activeConversationId"));const c=cs.find(x=>x.id===savedC)||cs.find(x=>x.project_id===p?.id);setProjectId(p?.id??null);setConversationId(c?.id??null);}catch(e){setError("Não foi possível conectar ao Mosaic Core: "+e.message);}finally{setLoading(false);}}
  useEffect(()=>{load();},[]);
  useEffect(()=>{
    let cancelled=false;
    async function refreshModelStatus(){
      try{
        const status=await api.models.status();
        if(!cancelled)setModelStatus(status);
      }catch{
        if(!cancelled)setModelStatus({provider:"ollama",online:false,running_models:[]});
      }
    }
    refreshModelStatus();
    const timer=setInterval(refreshModelStatus,5000);
    return ()=>{cancelled=true;clearInterval(timer);};
  },[]);

  useEffect(()=>{if(projectId)localStorage.setItem("mosaic.activeProjectId",String(projectId));},[projectId]);
  useEffect(()=>{if(conversationId)localStorage.setItem("mosaic.activeConversationId",String(conversationId));},[conversationId]);
  useEffect(()=>{
    let cancelled=false;
    async function loadMemories(){
      if(!projectId){setMemories([]);return;}
      try{
        const data=await api.memories.list(projectId);
        if(!cancelled)setMemories(data);
      }catch(err){
        if(!cancelled)setError("Não foi possível recuperar as memórias: "+err.message);
      }
    }
    loadMemories();
    return ()=>{cancelled=true;};
  },[projectId]);

  useEffect(()=>{
    let cancelled=false;
    async function loadMessages(){
      if(!conversationId){setMessages([]);return;}
      setMessagesLoading(true);
      try{
        const data=await api.conversations.messages(conversationId);
        if(!cancelled)setMessages(data);
      }catch(err){
        if(!cancelled)setError("Não foi possível recuperar o histórico: "+err.message);
      }finally{
        if(!cancelled)setMessagesLoading(false);
      }
    }
    loadMessages();
    return ()=>{cancelled=true;};
  },[conversationId]);


  function selectProject(id){setProjectId(id);setConversationId(conversations.find(c=>c.project_id===id)?.id??null);setProjectTab("Conversa");setMobile(false);}
  function selectConversation(id){const c=conversations.find(x=>x.id===id);setConversationId(id);if(c?.project_id)setProjectId(c.project_id);setMobile(false);}

  async function createProject(e){e.preventDefault();setSaving(true);const f=new FormData(e.currentTarget);const name=String(f.get("name")||"").trim();const description=String(f.get("description")||"").trim();try{const p=await api.projects.create({name,description:description||null,workspace:"./workspaces/"+slugify(name),metadata:{},state:{}});setProjects(x=>[...x,p]);setProjectId(p.id);setConversationId(null);setModal(null);}catch(err){setError(err.message);}finally{setSaving(false);}}
  async function createConversation(e){e.preventDefault();setSaving(true);const f=new FormData(e.currentTarget);const title=String(f.get("title")||"Nova conversa").trim()||"Nova conversa";const modelId=Number(f.get("model_id"))||models.find(m=>m.enabled)?.id;if(!modelId){setError("Nenhum modelo habilitado está registrado no Mosaic.");setSaving(false);return;}try{const c=await api.conversations.create({title,model_id:modelId,project_id:projectId});setConversations(x=>[c,...x]);setConversationId(c.id);setModal(null);}catch(err){setError(err.message);}finally{setSaving(false);}}

  async function sendMessage(content){
    if(!conversation||sending)return;
    setError("");
    setSending(true);
    const localUser={localId:`user-${Date.now()}`,role:"user",content,created_at:new Date().toISOString()};
    const localAssistant={localId:`assistant-${Date.now()}`,role:"assistant",content:"",created_at:new Date().toISOString()};
    setMessages(items=>[...items,localUser,localAssistant]);
    try{
      let streamed="";
      await api.conversations.stream(conversation.id,content,chunk=>{
        streamed+=chunk;
        setMessages(items=>items.map(item=>item.localId===localAssistant.localId?{...item,content:streamed}:item));
      });
      const persisted=await api.conversations.messages(conversation.id);
      setMessages(persisted);
      setConversations(items=>items.map(item=>item.id===conversation.id?{...item,updated_at:new Date().toISOString()}:item));
    }catch(err){
      setMessages(items=>items.filter(item=>item.localId!==localAssistant.localId));
      setError("Não foi possível concluir a resposta: "+err.message);
    }finally{
      setSending(false);
    }
  }

  async function changeConversationModel(modelId){if(!conversation)return;setError("");try{const updated=await api.conversations.update(conversation.id,{model_id:modelId});setConversations(items=>items.map(item=>item.id===updated.id?updated:item));}catch(err){setError("Não foi possível trocar o modelo: "+err.message);}}
  async function saveModel(e){
    e.preventDefault();setSaving(true);setError("");
    const f=new FormData(e.currentTarget);
    const id=Number(f.get("id")); const configuration={
      temperature:Number(f.get("temperature")), top_p:Number(f.get("top_p")), top_k:Number(f.get("top_k")),
      num_ctx:Number(f.get("num_ctx")), num_predict:Number(f.get("num_predict"))
    };
    try{
      const updated=await api.models.update(id,{name:String(f.get("name")).trim(),configuration,enabled:f.get("enabled")==="on"});
      setModels(items=>items.map(item=>item.id===updated.id?updated:item));
      setModal(null);
    }catch(err){setError("Não foi possível salvar o modelo: "+err.message);}finally{setSaving(false);}
  }
  async function createModel(e){
    e.preventDefault();setSaving(true);setError("");
    const f=new FormData(e.currentTarget);
    const configuration={temperature:Number(f.get("temperature")),top_p:Number(f.get("top_p")),top_k:Number(f.get("top_k")),num_ctx:Number(f.get("num_ctx")),num_predict:Number(f.get("num_predict"))};
    try{
      const created=await api.models.create({name:String(f.get("name")).trim(),provider:String(f.get("provider")).trim(),model_name:String(f.get("model_name")).trim(),configuration,enabled:true});
      setModels(items=>[...items,created]);setModal({type:"model",modelId:created.id}); 
    }catch(err){setError("Não foi possível cadastrar o modelo: "+err.message);}finally{setSaving(false);}
  }

  return <div className="app-shell"><Sidebar projects={projects} conversations={projectConversations} activeProjectId={projectId} activeConversationId={conversationId} onProject={selectProject} onConversation={selectConversation} onNewProject={()=>setModal("project")} onNewConversation={()=>setModal("conversation")} onModelSettings={()=>setModal({type:"models"})} onHelp={()=>setModal({type:"help"})} mobileOpen={mobile} onClose={()=>setMobile(false)}/>{mobile&&<button className="mobile-overlay" onClick={()=>setMobile(false)} aria-label="Fechar menu"/>}
    <div className="app-main"><TopBar onMenu={()=>setMobile(true)} project={project} conversation={conversation} models={models} onModelChange={changeConversationModel} modelStatus={modelStatus} onModelSettings={()=>setModal({type:"models"})} onContext={setContextTab}/><div className="workspace-grid"><main className="workspace"><ProjectHeader project={project} tab={projectTab} setTab={setProjectTab}/>{error&&<div className="api-error">{error}<button onClick={load}>Tentar novamente</button></div>}<div className="chat-scroll">{loading?<div className="loading-state">Conectando ao Mosaic Core…</div>:!conversation?<div className="conversation-empty"><MosaicMark compact/><h2>Workspace pronto</h2><p>{project ? "Projeto ativo: "+project.name+"." : "Crie ou selecione um projeto para começar."}</p>{!conversation&&<button className="empty-action" onClick={()=>setModal("conversation")} disabled={!project||!models.some(m=>m.enabled)}><Icon name="plus" size={16}/>Nova conversa</button>}</div>:messagesLoading?<div className="loading-state">Recuperando histórico…</div>:<MessageList messages={messages} streaming={sending}/>} </div><Composer disabled={!conversation||sending} model={model} onSubmit={sendMessage}/></main><ContextPanel tab={contextTab} setTab={setContextTab} project={project} conversation={conversation} model={model} memoryCount={memories.length} messageCount={messages.length} memories={memories}/></div></div>
    {modal?.type==="help"&&<Modal title="Ajuda" onClose={()=>setModal(null)}><div className="modal-form"><p className="modal-hint">O Mosaic é uma interface conectada ao Mosaic Core. O estado persistente vem do backend; esta interface apresenta e controla esse estado.</p><div className="help-block"><strong>Começando</strong><span>Crie um projeto, depois crie uma conversa e selecione um modelo registrado no Core.</span></div><div className="help-block"><strong>Modelos</strong><span>Use Configurações para cadastrar e ajustar modelos. O status no topo consulta o Ollama quando o provider é Ollama.</span></div><div className="help-block"><strong>Contexto</strong><span>O painel lateral mostra projeto, modelo, memória e histórico reais da conversa ativa.</span></div></div></Modal>}
    {modal?.type==="models"&&<Modal title="Modelos e configurações" onClose={()=>!saving&&setModal(null)}><div className="modal-form"><p className="modal-hint">Os valores abaixo são persistidos no Core e enviados ao provider quando a conversa usa este modelo.</p>{models.map(m=><button key={m.id} type="button" className="related-item" onClick={()=>setModal({type:"model",modelId:m.id})}><span className="status-dot"/><span>{m.name}</span><span className="model-provider">{m.provider} · {m.model_name}</span></button>)}<button type="button" className="primary-action" onClick={()=>setModal({type:"new-model"})}>+ Cadastrar modelo</button></div></Modal>}
    {modal?.type==="model"&&(()=>{const m=models.find(x=>x.id===modal.modelId);if(!m)return null;const c=m.configuration||{};return <Modal title={"Configurar "+m.name} onClose={()=>!saving&&setModal(null)}><form className="modal-form modal-wide" onSubmit={saveModel}><input type="hidden" name="id" value={m.id}/><label>Nome<input name="name" defaultValue={m.name} required/></label><div className="model-config-grid"><label>Temperature<input type="number" name="temperature" step="0.1" min="0" max="2" defaultValue={c.temperature ?? 0.7}/></label><label>Top P<input type="number" name="top_p" step="0.05" min="0" max="1" defaultValue={c.top_p ?? 0.9}/></label><label>Top K<input type="number" name="top_k" min="0" max="100" defaultValue={c.top_k ?? 40}/></label><label>Contexto<input type="number" name="num_ctx" min="256" max="131072" defaultValue={c.num_ctx ?? 4096}/></label><label>Máx. tokens<input type="number" name="num_predict" min="-1" max="131072" defaultValue={c.num_predict ?? -1}/></label><label className="model-config-toggle">Ativo<input type="checkbox" name="enabled" defaultChecked={m.enabled}/></label></div><p className="model-config-status">Provider: {m.provider} · Modelo local: {m.model_name}</p><div className="modal-actions"><button type="button" onClick={()=>setModal({type:"models"})}>Voltar</button><button className="primary-action" disabled={saving}>{saving?"Salvando…":"Salvar configurações"}</button></div></form></Modal>})()}
    {modal?.type==="new-model"&&<Modal title="Cadastrar modelo" onClose={()=>!saving&&setModal(null)}><form className="modal-form modal-wide" onSubmit={createModel}><div className="model-config-grid"><label>Nome<input name="name" required autoFocus placeholder="Ex.: Llama 3.2 3B"/></label><label>Provider<input name="provider" defaultValue="ollama" required/></label><label className="full">Identificador do modelo<input name="model_name" required placeholder="Ex.: llama3.2:3b"/></label><label>Temperature<input type="number" name="temperature" step="0.1" min="0" max="2" defaultValue="0.7"/></label><label>Top P<input type="number" name="top_p" step="0.05" min="0" max="1" defaultValue="0.9"/></label><label>Top K<input type="number" name="top_k" min="0" max="100" defaultValue="40"/></label><label>Contexto<input type="number" name="num_ctx" min="256" max="131072" defaultValue="4096"/></label><label>Máx. tokens<input type="number" name="num_predict" min="-1" max="131072" defaultValue="-1"/></label></div><div className="modal-actions"><button type="button" onClick={()=>setModal({type:"models"})}>Cancelar</button><button className="primary-action" disabled={saving}>{saving?"Cadastrando…":"Cadastrar modelo"}</button></div></form></Modal>}
    {modal==="project"&&<Modal title="Novo projeto" onClose={()=>!saving&&setModal(null)}><form className="modal-form" onSubmit={createProject}><label>Nome<input name="name" required autoFocus placeholder="Ex.: Guitar Livre"/></label><label>Descrição<textarea name="description" rows="3" placeholder="O que estamos construindo?"/></label><div className="modal-actions"><button type="button" onClick={()=>setModal(null)}>Cancelar</button><button className="primary-action" disabled={saving}>{saving?"Criando…":"Criar projeto"}</button></div></form></Modal>}
    {modal==="conversation"&&<Modal title="Nova conversa" onClose={()=>!saving&&setModal(null)}><form className="modal-form" onSubmit={createConversation}><p className="modal-hint">Projeto: <strong>{project?.name || "Nenhum projeto"}</strong></p><label>Título<input name="title" required autoFocus placeholder="Ex.: Arquitetura do projeto"/></label><label>Modelo<select name="model_id" defaultValue={models.find(m=>m.enabled)?.id ?? ""} required><option value="" disabled>Selecione um modelo</option>{models.filter(m=>m.enabled).map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label><div className="modal-actions"><button type="button" onClick={()=>setModal(null)}>Cancelar</button><button className="primary-action" disabled={saving||!project||!models.some(m=>m.enabled)}>{saving?"Criando…":"Criar conversa"}</button></div></form></Modal>}
  </div>;
}
