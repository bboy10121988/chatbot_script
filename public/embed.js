(function(){
  var API_BASE = window.CHATBOT_API_BASE || "/v1";
  var API_KEY = window.CHATBOT_API_KEY || "";
  var btn = document.createElement('button');
  btn.innerText = '聊天咨詢';
  btn.style = 'position:fixed;right:24px;bottom:24px;z-index:9999;padding:10px 14px;border-radius:20px;background:#1f8fff;color:#fff;border:none;cursor:pointer;';
  document.body.appendChild(btn);
  var panel = document.createElement('div');
  panel.style = 'position:fixed;right:24px;bottom:72px;width:360px;height:520px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.1);display:none;z-index:9999;overflow:hidden;';
  panel.innerHTML = '<div id="chat" style="height:100%;display:flex;flex-direction:column">\
      <div id="msgs" style="flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:6px;background:#f9fafb"></div>\
      <div style="display:flex;border-top:1px solid #eee">\
        <input id="inp" style="flex:1;padding:10px;border:0;outline:none" placeholder="說點什麼...（例如：藍牙耳機、充電器）"/>\
        <button id="send" style="padding:0 12px;border:0;background:#1f8fff;color:#fff">發送</button>\
      </div></div>';
  document.body.appendChild(panel);
  var conversationId = localStorage.getItem('cb_conversation_id') || null;
  var welcomed = false;
  var welcomeText = null;
  // Expose a reset helper for admin page
  window.ChatbotEmbedReset = async function(){
    try {
      if (conversationId){
        await fetch(API_BASE.replace(/\/$/, '') + '/chat/reset', { method:'POST', headers: { 'Content-Type':'application/json','X-API-Key':API_KEY }, body: JSON.stringify({ conversation_id: conversationId }) });
      }
    } catch (e) {}
    try { localStorage.removeItem('cb_conversation_id'); } catch (e) {}
    conversationId = null;
    welcomed = false;
    welcomeText = null;
    var m = msgs(); if (m) m.innerHTML = '';
    if (panel && panel.style.display !== 'none') { ensureWelcome(); }
  };
  function msgs(){ return document.getElementById('msgs'); }
  function bubble(who, text){
    var wrap=document.createElement('div');
    wrap.style='display:flex;'+(who==='user'?'justify-content:flex-end;':'justify-content:flex-start;');
    var b=document.createElement('div');
    b.style=(who==='user'
      ?'max-width:78%;background:#1f8fff;color:#fff;padding:8px 10px;border-radius:12px 12px 2px 12px;'
      :'max-width:78%;background:#e5e7eb;color:#111827;padding:8px 10px;border-radius:12px 12px 12px 2px;');
    b.style.fontSize='14px'; b.textContent=text; wrap.appendChild(b); return wrap;
  }
  function addMsg(who, text){ msgs().appendChild(bubble(who, text)); msgs().scrollTop=msgs().scrollHeight; }
  async function ensureWelcome(){
    try{
      // Always refetch to reflect latest admin changes
      const res = await fetch(API_BASE.replace(/\/$/, '') + '/settings', { headers: { 'X-API-Key': API_KEY }});
      if(res.ok){ const data = await res.json(); welcomeText = (data && data.welcome_text) || null; }
    }catch(e){}
    if(!conversationId && !welcomed){
      // 首次會話，同步以氣泡再提示一次
      addMsg('assistant', welcomeText || '嗨～我可以幫你快速找商品。試試輸入關鍵字：藍牙耳機、耳機、充電器…');
      welcomed = true;
    }
  }
  // suggestion chips
  function renderChips(list){
    if (!Array.isArray(list) || !list.length) return;
    var bar = document.createElement('div');
    bar.style='display:flex;gap:8px;flex-wrap:wrap;padding:8px 12px;border-top:1px dashed #e5e7eb;background:#fafafa;';
    list.slice(0,6).forEach(function(q){
      var chip=document.createElement('button'); chip.textContent=q; chip.style='border:1px solid #e5e7eb;background:#fff;color:#111827;border-radius:999px;padding:6px 10px;cursor:pointer;font-size:12px;';
      chip.onclick=function(){ document.getElementById('inp').value=q; document.getElementById('send').click(); };
      bar.appendChild(chip);
    });
    panel.querySelector('#chat').appendChild(bar);
  }
  btn.onclick = function(){
    var visible = panel.style.display !== 'none';
    panel.style.display = visible ? 'none' : 'block';
    if(!visible){ ensureWelcome().then(function(){
      // load suggestions from settings
      fetch(API_BASE.replace(/\/$/, '') + '/settings', { headers: { 'X-API-Key': API_KEY }}).then(function(r){ return r.json(); }).then(function(d){
        if (d && Array.isArray(d.suggested_queries)) renderChips(d.suggested_queries);
      }).catch(function(){});
    }); }
  };
  document.getElementById('send').onclick = async function(){
    var inp = document.getElementById('inp');
    var val = (inp.value||'').trim(); if(!val) return; addMsg('user', val); inp.value='';
    // typing indicator
    var typingEl = bubble('assistant','正在為你查找…'); typingEl.id='typing_ind'; msgs().appendChild(typingEl); msgs().scrollTop=msgs().scrollHeight;
    var res = await fetch(API_BASE + '/chat/message', { method:'POST', headers:{ 'Content-Type':'application/json','X-API-Key':API_KEY }, body: JSON.stringify({conversation_id:conversationId, message:val, locale: navigator.language}) });
    var data = await res.json(); if(data.conversation_id && data.conversation_id!==conversationId){ conversationId = data.conversation_id; localStorage.setItem('cb_conversation_id', conversationId); }
    var tEl=document.getElementById('typing_ind'); if(tEl){ tEl.remove(); }
    (data.messages||[]).forEach(function(m){ if(m.type==='text') addMsg('assistant', m.content); });
    (data.products||[]).forEach(function(p){ var c=document.createElement('div'); c.style='align-self:flex-start;border:1px solid #eee;padding:8px;border-radius:8px;margin:2px 0;display:flex;gap:8px;align-items:center;font-size:13px;background:#fff;'; c.innerHTML='<img src="'+(p.image_url||'')+'" style="width:48px;height:48px;object-fit:cover;border-radius:6px"/>\
        <div style="flex:1">'+p.name+'<div style="color:#6b7280">￥'+(((p.price||{}).value)||'')+'</div></div>\
        <button style="background:#10b981;color:#fff;border:0;border-radius:6px;padding:6px 10px;cursor:pointer">加入</button>'; var b=c.querySelector('button'); b.onclick=async function(){ await fetch(API_BASE+'/cart/items',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':API_KEY},body:JSON.stringify({conversation_id:conversationId,product_id:p.id,quantity:1})}); }; msgs().appendChild(c); msgs().scrollTop=msgs().scrollHeight; });
  };
})();
