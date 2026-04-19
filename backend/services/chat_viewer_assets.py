"""Browser assets for generated chat archive entrypoints."""

from __future__ import annotations

VIEWER_CSS = """
:root{color-scheme:light;--bg:#f5f3ef;--panel:#fffdfa;--ink:#211f1d;--muted:#756f68;--line:#d9d1c8;--user:#1f6f5b;--assistant:#26211d;--tool:#5b4d3d;--code:#171717}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:inherit}.shell{min-height:100vh}.topbar{position:sticky;top:0;z-index:2;background:rgba(245,243,239,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}.topbar-inner{max-width:1040px;margin:0 auto;padding:18px 20px;display:flex;gap:16px;align-items:center;justify-content:space-between}.crumb{font-size:13px;color:var(--muted);text-decoration:none}h1{margin:4px 0 6px;font-size:28px;line-height:1.15}.meta{display:flex;flex-wrap:wrap;gap:8px;color:var(--muted);font-size:13px}.pill{border:1px solid var(--line);border-radius:999px;padding:4px 8px;background:var(--panel)}
.actions{display:flex;gap:8px;align-items:center}.button{height:34px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);padding:0 11px;font:inherit;cursor:pointer}.button:hover,.session:hover{border-color:#9c8e7e}.messages{max-width:960px;margin:0 auto;padding:26px 20px 64px}.message-row{display:flex;margin:18px 0}.message-row.user{justify-content:flex-end}.message-row.assistant,.message-row.system{justify-content:flex-start}.message-row.tool{justify-content:center}.bubble{max-width:min(760px,86%);border:1px solid var(--line);border-radius:8px;background:var(--panel);box-shadow:0 1px 2px rgba(0,0,0,.03);overflow:hidden}.user .bubble{background:#f0faf6;border-color:#b8d9cd}.assistant .bubble{background:#fffdfa}.system .bubble{background:#f7f0e7}.tool .bubble{max-width:860px;width:100%;background:#fbf7f0;border-style:dashed}
.bubble-head{display:flex;gap:10px;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(0,0,0,.06);padding:9px 12px;color:var(--muted);font-size:12px}.role{font-weight:700;text-transform:uppercase;letter-spacing:.04em}.user .role{color:var(--user)}.assistant .role{color:var(--assistant)}.tool .role{color:var(--tool)}.bubble-body{padding:12px 14px}.text-block{font-size:15px;line-height:1.58;white-space:pre-wrap;overflow-wrap:anywhere}.text-block+*,.image-wrap+*,.code-wrap+*,details+*{margin-top:12px}.code-wrap{background:var(--code);border-radius:8px;overflow:hidden;border:1px solid #2f2f2f}.code-lang{color:#c8c2b9;background:#242424;border-bottom:1px solid #333;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;padding:6px 10px}pre{margin:0;overflow:auto;padding:12px;color:#f4f1ec;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}
.image-wrap{border:1px solid var(--line);border-radius:8px;background:#eee8df;overflow:hidden}.image-wrap img{display:block;max-width:100%;max-height:520px;margin:0 auto}.caption{padding:7px 9px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}details.tool-card{border:1px solid var(--line);border-radius:8px;background:rgba(255,255,255,.55);overflow:hidden}details.tool-card summary{cursor:pointer;padding:9px 11px;font-size:13px;color:var(--tool);font-weight:700}.tool-card pre{background:#211f1d;max-height:360px}.empty,.error{max-width:960px;margin:24px auto;padding:16px 20px;color:var(--muted)}.index-main{max-width:1040px;margin:0 auto;padding:30px 20px 64px}.search{width:100%;height:40px;border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:0 12px;font:inherit;margin:12px 0 18px}.sessions{display:grid;gap:10px}.session{display:block;text-decoration:none;border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:14px}.session-title{font-weight:750;margin-bottom:7px}.session-preview{color:var(--muted);font-size:13px;display:flex;flex-wrap:wrap;gap:8px}
@media (max-width:720px){.topbar-inner{align-items:flex-start;flex-direction:column}.actions{width:100%}.button{flex:1}.bubble{max-width:94%}h1{font-size:23px}.messages{padding-left:12px;padding-right:12px}}
"""

VIEWER_JS = r"""
(function(){
  function byId(id){return document.getElementById(id);}
  function text(value){return value == null ? "" : String(value);}
  function basename(value){return text(value).replace(/\\/g,"/").split("/").filter(Boolean).pop() || text(value);}
  function assetUrl(value){
    const src = text(value); return !src || /^(data:|https?:|blob:)/i.test(src) ? src : basename(src);
  }
  function hasPayload(value){return value && (Array.isArray(value) || Object.keys(value).length > 0);}
  function loadJson(url, fallback){
    return fetch(url,{cache:"no-store"}).then(function(response){
      if(!response.ok) throw new Error(response.status+" "+response.statusText);
      return response.json();
    }).catch(function(error){
      if(hasPayload(fallback)) return fallback;
      error.message = location.protocol === "file:" ? "Browser blocked local JSON loading. Open this archive through TenderClaw /tenderclaw/chats." : error.message;
      throw error;
    });
  }
  function clear(node){while(node.firstChild) node.removeChild(node.firstChild);}
  function addClass(node,name){if(name) node.classList.add(name);}
  function appendTextBlock(parent, value){
    const raw = text(value);
    if(!raw.trim()) return;
    const parts = raw.split(/```([\w.+-]*)\n?([\s\S]*?)```/g);
    for(let i=0;i<parts.length;i+=3){
      appendPlain(parent, parts[i]);
      if(i+2 < parts.length) appendCode(parent, parts[i+2], parts[i+1]);
    }
  }
  function appendPlain(parent, value){
    const valueText = text(value); if(!valueText.trim()) return;
    const div = document.createElement("div"); div.className = "text-block"; div.textContent = valueText; parent.appendChild(div);
  }
  function appendCode(parent, code, lang){
    const wrap = document.createElement("div"); wrap.className = "code-wrap";
    if(text(lang).trim()){
      const label = document.createElement("div"); label.className = "code-lang"; label.textContent = text(lang).trim(); wrap.appendChild(label);
    }
    const pre = document.createElement("pre"), codeEl = document.createElement("code");
    codeEl.textContent = text(code).replace(/\n$/,""); pre.appendChild(codeEl); wrap.appendChild(pre); parent.appendChild(wrap);
  }
  function appendImage(parent, block){
    const src = assetUrl(block.source || (block.image_url && block.image_url.url) || block.url || block.path);
    if(!src) return appendJson(parent, block);
    const wrap = document.createElement("figure"), img = document.createElement("img"), caption = document.createElement("figcaption");
    const label = block.name || (/^data:/i.test(src) ? block.mime_type : basename(src)) || "Image";
    wrap.className = "image-wrap"; img.src = src; img.alt = label;
    caption.className = "caption"; caption.textContent = label;
    wrap.append(img, caption); parent.appendChild(wrap);
  }
  function appendAttachment(parent, block){
    const href = assetUrl(block.path || block.source || block.url || block.saved_path);
    if(!href) return appendJson(parent, block);
    const link = document.createElement("a"); link.className = "button"; link.href = href; link.textContent = block.name || basename(href) || "Attachment"; parent.appendChild(link);
  }
  function appendJson(parent, value){
    appendCode(parent, JSON.stringify(value, null, 2), "json");
  }
  function appendTool(parent, block, kind){
    const details = document.createElement("details"), summary = document.createElement("summary");
    details.className = "tool-card"; summary.textContent = kind === "use" ? "Tool: " + text(block.name || "tool") : "Tool result";
    details.appendChild(summary); appendCode(details, kind === "use" ? JSON.stringify(block.input || {}, null, 2) : text(block.content || ""), kind === "use" ? "json" : "text"); parent.appendChild(details);
  }
  function appendBlock(parent, block){
    if(typeof block === "string") return appendTextBlock(parent, block);
    if(!block || typeof block !== "object") return;
    if(block.type === "text") return appendTextBlock(parent, block.text);
    if(block.type === "thinking") return appendTool(parent, {name:"thinking", input:{thinking:block.thinking || ""}}, "use");
    if(block.type === "tool_use") return appendTool(parent, block, "use");
    if(block.type === "tool_result") return appendTool(parent, block, "result");
    if(block.type === "image" || block.type === "image_url") return appendImage(parent, block);
    if(block.type === "file" || block.type === "attachment") return appendAttachment(parent, block);
    appendJson(parent, block);
  }
  function blocksOf(message){return Array.isArray(message.content) ? message.content : [message.content || ""];}
  function visualRole(message){
    const blocks = blocksOf(message);
    if(blocks.length && blocks.every(function(block){return block && block.type === "tool_result";})) return "tool";
    return message.role || "assistant";
  }
  function renderMessage(parent, message, index){
    const row = document.createElement("article");
    const role = visualRole(message);
    row.className = "message-row";
    addClass(row, role);
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const head = document.createElement("div");
    head.className = "bubble-head";
    const label = document.createElement("span");
    label.className = "role";
    label.textContent = role === "user" ? "You" : role === "tool" ? "Tool" : role === "system" ? "System" : "TenderClaw";
    const count = document.createElement("span");
    count.textContent = "#"+(index+1);
    head.append(label, count);
    const body = document.createElement("div");
    body.className = "bubble-body";
    blocksOf(message).forEach(function(block){appendBlock(body, block);});
    bubble.append(head, body);
    row.appendChild(bubble);
    parent.appendChild(row);
  }
  function renderConversation(data){
    data = data || {};
    const title = byId("title"), meta = byId("meta"), messages = byId("messages");
    clear(messages);
    const items = Array.isArray(data.messages) ? data.messages : [];
    title.textContent = data.title || data.session_id || "TenderClaw session";
    meta.innerHTML = "";
    [data.model || "model unknown", items.length+" messages", data.updated_at || data.created_at || ""]
      .filter(Boolean).forEach(function(value){
        const span = document.createElement("span");
        span.className = "pill";
        span.textContent = value;
        meta.appendChild(span);
      });
    if(!items.length){
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No messages in this archive yet.";
      messages.appendChild(empty);
      return;
    }
    items.forEach(function(message, index){renderMessage(messages, message, index);});
  }
  function showError(target, error){
    clear(target); const div = document.createElement("div"); div.className = "error"; div.textContent = "Unable to load JSON: " + error.message; target.appendChild(div);
  }
  function addPicker(target, render, label){
    if(location.protocol !== "file:") return;
    const box = document.createElement("div"), input = document.createElement("input");
    box.className = "error"; box.textContent = "Choose " + label + " from this folder: ";
    input.type = "file"; input.accept = ".json,application/json";
    input.addEventListener("change", function(){
      const file = input.files && input.files[0]; if(!file) return;
      file.text().then(function(raw){render(JSON.parse(raw));}).catch(function(error){showError(target, error);});
    });
    box.appendChild(input); target.appendChild(box);
  }
  function bootSession(options){
    const target = byId("messages"), reload = byId("reload");
    function run(){loadJson(options.jsonUrl || "conversation.json", options.fallback).then(renderConversation).catch(function(error){showError(target,error);addPicker(target,renderConversation,"conversation.json");});}
    if(reload) reload.addEventListener("click", run); run();
  }
  function renderSessions(data){
    data = data || {};
    const list = byId("sessions"), search = byId("search");
    const sessions = Array.isArray(data.sessions) ? data.sessions : [];
    function draw(){
      const needle = text(search && search.value).toLowerCase();
      clear(list);
      sessions.filter(function(session){return !needle || JSON.stringify(session).toLowerCase().includes(needle);})
        .forEach(function(session){
          const link = document.createElement("a"), title = document.createElement("div"), meta = document.createElement("div");
          link.className = "session"; link.href = session.href || "#";
          title.className = "session-title"; title.textContent = session.title || session.session_id || "Untitled session";
          meta.className = "session-preview";
          [session.model || "model unknown", (session.message_count || 0)+" messages", session.updated_at || session.created_at || ""].forEach(function(value){
            const span = document.createElement("span");
            span.textContent = value;
            meta.appendChild(span);
          });
          link.append(title, meta);
          list.appendChild(link);
        });
    }
    if(search) search.addEventListener("input", draw);
    draw();
  }
  function bootIndex(options){
    const target = byId("sessions");
    loadJson(options.jsonUrl || "sessions.json", options.fallback).then(renderSessions).catch(function(error){showError(target,error);addPicker(target,renderSessions,"sessions.json");});
  }
  window.TenderClawChatViewer = {bootSession:bootSession,bootIndex:bootIndex};
})();
"""
