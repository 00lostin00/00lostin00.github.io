/* lost.in native Butterfly integration. Independent public viewer for AlgoArchive-shaped records. */
(() => {
 'use strict';
 const $ = id => document.getElementById(id);
 const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const url = value => {try{const x=new URL(String(value));return ['https:','http:'].includes(x.protocol)?esc(x.href):'#';}catch(_){return '#';}};
 const dt = text => {if(!text)return '—';const date=new Date(text);return isNaN(date.getTime())?esc(String(text).slice(0,10)):new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'}).format(date);};
 const empty = (message='暂无记录') => `<div class="aa-empty"><i class="fas fa-inbox"></i><p>${esc(message)}</p></div>`;
 const state={public:null,local:null,view:'home',platform:'all',search:'',status:'all',page:1,limit:50,sort:'recent',localPreview:[],analysisPlatform:'all',analysisYear:'rolling',liveEndpoint:'',refreshing:false,catalog:null,blog:null,catalogEndpoint:'',catalogRefreshing:false,blogPage:1,practicePage:1,practiceYear:'all',practiceSeries:'all',practiceStage:'all',practiceSearch:'',eventPage:1,eventMode:'upcoming',eventPlatform:'all'};
 const platformId = value => String(value || 'other').trim().toLowerCase().replace(/^niuke$/, 'nowcoder');
 function allPlatforms() {
   const items = new Map((state.public?.platforms || []).map(p => [p.id, p]));
   for (const p of [...(state.local?.problems || []), ...(state.local?.contests || []), ...state.localPreview]) {
     const id = platformId(p.platform);
     if (!items.has(id)) items.set(id, {id, name:id, short:id.slice(0,4).toUpperCase(), group:'本地归档', mode:'manual', sync_status:'manual'});
   }
   return [...items.values()];
 }
 const platform = id => allPlatforms().find(p=>p.id===id) || {id,name:id||'其他 OJ',short:(id||'OJ').slice(0,3).toUpperCase(),home:'',sync_status:'manual',mode:'manual'};
 const statusLabel = {AC:'已通过',TODO:'待完成',REVIEW:'需复习',WA:'未通过',ARCHIVED:'本地归档'};
 const statusClass = v => v==='AC'?'aa-good':v==='REVIEW'?'aa-warn':'aa-muted';
 function records(){
   const primary=(state.public?.problems || []).map(p=>({...p,origin:p.source==='api'?'api':'manual'}));
   const archive=(state.local?.problems || []).map(p=>({
     platform: platformId(p.platform),
     id:p.number||p.id,archive_id:p.id,title:p.name||p.number||'未命名题目',url:p.url||'',
     language:p.language,status:'ARCHIVED',accepted_at:p.updated_at||null,
     rating:null,level:'',tags:[],code:p.code,algorithm_id:p.algorithm_id,contest_id:p.contest_id,
     origin:'archive'}));
   const map=new Map();
   for(const p of primary){map.set(`${p.platform}:${String(p.id).toLowerCase()}`,p);}
   for(const p of archive){
     const key=`${p.platform}:${String(p.id).toLowerCase()}`;
     const old=map.get(key);
     if(old){map.set(key,{...old,code:p.code,archive_id:p.archive_id,algorithm_id:p.algorithm_id,contest_id:p.contest_id,language:p.language,hasArchive:true});}
     else map.set(key,p);
   }
   for(const p of state.localPreview){const key=`${p.platform}:${String(p.id).toLowerCase()}`;if(!map.has(key))map.set(key,p);}
   return [...map.values()];
 }
 function contests(){
   const entries=[...(state.public?.contests||[]).map(c=>({...c,origin:c.source||'api'})),
     ...(state.local?.contests||[]).map(c=>({...c,platform:platformId(c.platform),date:c.updated_at,origin:'archive'}))];
   const seen=new Set();return entries.filter(c=>{const key=c.platform+'|'+(c.url||c.id||c.title);if(seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>(b.date||'').localeCompare(a.date||''));
 }
 function viewHeader(label,description,action=''){
   return `<div class="aa-section-head"><div><h2>${esc(label)}</h2><p>${esc(description)}</p></div>${action}</div>`;
 }
 function badge(id){const p=platform(id);return `<span class="aa-platform-badge">${esc(p.short||p.name)}</span>`;}
 function tags(list,max=2){const items=Array.isArray(list)?list:[];return items.length?items.slice(0,max).map(t=>`<span class="aa-tag">${esc(t)}</span>`).join(' '):'<span class="aa-dim">—</span>';}
 function rating(v){const n=Number(v);return v!=null&&Number.isFinite(n)?`<span class="aa-rating">${n}</span>`:'<span class="aa-dim">—</span>';}
 function problemRows(list){if(!list.length)return `<tr><td colspan="5">${empty('该条件下暂无题目。支持手动归档，也可配置自动同步。')}</td></tr>`;
   return list.map(p=>`<tr><td><div class="aa-problem-name"><span class="aa-number">${esc(p.id)}</span><a href="${url(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title||p.id)}</a></div>${p.notes?`<small class="aa-dim">${esc(p.notes)}</small>`:''}${p.code?`<details class="aa-code"><summary>查看已公开的代码</summary><pre><code>${esc(p.code)}</code></pre></details>`:''}</td><td>${badge(p.platform)}</td><td><span class="aa-status ${statusClass(p.status)}">${esc(statusLabel[p.status]||p.status||'归档')}</span></td><td>${rating(p.rating)}${p.level?`<small class="aa-dim">${esc(p.level)}</small>`:''}</td><td class="aa-last">${dt(p.accepted_at||p.updated_at)}</td></tr>`).join('');
 }
 function problemTable(items){return `<div class="aa-table-scroller"><table class="aa-table"><thead><tr><th>题目</th><th>平台</th><th>状态</th><th>难度</th><th>日期</th></tr></thead><tbody>${problemRows(items)}</tbody></table></div>`;}
 function platformCards(list){return `<div class="aa-oj-grid">${list.map(p=>{const n=records().filter(r=>r.platform===p.id);const ac=n.filter(r=>r.status==='AC').length;const sync=p.mode==='auto'?(p.sync_status==='ok'?'自动已同步':p.sync_status==='partial'?'部分同步':['error','blocked'].includes(p.sync_status)?'同步受限':p.handle?'待同步':'未配置账号'):'手动归档';return `<button class="aa-oj-card" data-aa-oj="${esc(p.id)}" data-aa-view="problems" type="button"><span class="aa-oj-icon">${esc(p.short||p.id.slice(0,2))}</span><span class="aa-oj-info"><b>${esc(p.name)}</b><small>${esc(sync)}</small></span><span class="aa-oj-count">${p.mode==='auto'&&!p.last_ok&&['error','blocked','not_configured'].includes(p.sync_status)?'—':ac}<small>AC</small></span></button>`;}).join('')}</div>`;}
 function chart(){const points=state.public?.ratings?.codeforces?.history||[];const good=points.filter(p=>p.rating!=null&&p.time).map(p=>({...p,rating:Number(p.rating)}));if(good.length<2)return empty('有至少两场 Rated 比赛后显示 Rating 曲线');const w=700,h=160,pad=20,min=Math.min(...good.map(p=>p.rating)),max=Math.max(...good.map(p=>p.rating));const spread=Math.max(1,max-min);const coords=good.map((p,i)=>[pad+i*(w-2*pad)/(good.length-1),h-pad-(p.rating-min)/spread*(h-2*pad)]);const line=coords.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');return `<svg class="aa-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Codeforces Rating 变化曲线"><path d="M20 ${h-pad} H${w-pad}" class="aa-chart-axis"/><path d="${line}" class="aa-chart-line" fill="none" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${coords[coords.length-1][0]}" cy="${coords[coords.length-1][1]}" r="5" class="aa-chart-dot"/><text x="${w-pad}" y="${h-3}" text-anchor="end" class="aa-chart-text">${esc(good[good.length-1].rating)} · ${dt(good[good.length-1].time)}</text><text x="20" y="15" class="aa-chart-text">MAX ${max}</text></svg>`;}
 function analysisPanel(){return globalThis.AAInsights?AAInsights.render({problems:records(),platforms:allPlatforms(),tagSync:state.public?.tag_sync,platform:state.analysisPlatform,year:state.analysisYear}):'';}
 function home(){const ps=records(),ct=contests(),ac=ps.filter(p=>p.status==='AC'),ar=state.local?.algorithms||[];const cf=state.public?.ratings?.codeforces||{};const recent=[...ac].sort((a,b)=>(b.accepted_at||'').localeCompare(a.accepted_at||'')).slice(0,8);const fav=['codeforces','atcoder','nowcoder','luogu','acwing'].map(platform).filter(p=>p.id);return `
  <div class="aa-stats"><div class="aa-stat"><span>AC 题目</span><strong>${ac.length}</strong><small>按平台 + 题号去重</small></div><div class="aa-stat"><span>比赛记录</span><strong>${ct.length}</strong><small>自动 + 手动归档</small></div><div class="aa-stat"><span>算法模板</span><strong>${ar.length}</strong><small>由本地 AlgoArchive 导出</small></div><div class="aa-stat"><span>Codeforces Rating</span><strong>${esc(cf.current??'—')}</strong><small>最高 ${esc(cf.max??'—')}</small></div></div>
  ${analysisPanel()}${viewHeader('平台工作区','按 OJ 分类整理和回顾题目')}${platformCards(fav)}
  <div class="aa-block">${viewHeader('最近通过的题目','自动同步的 AC 和手动归档的通过记录','<button class="aa-text-button" data-aa-view="problems" data-aa-oj="all">浏览全部 →</button>')}${problemTable(recent)}</div>
  <div class="aa-block aa-chart-block">${viewHeader('Codeforces 评分轨迹','使用公开 Rating 历史生成')}${chart()}</div>`;}
 function platforms(){const ps=allPlatforms(),groups=[...new Set(ps.map(p=>p.group||'其他'))];return `${viewHeader('全部 OJ 工作区',`统一管理 ${ps.length} 个平台；无接口的平台采用手动归档`)}`+groups.map(g=>`<div class="aa-block"><h3 class="aa-subheading">${esc(g)}</h3>${platformCards(ps.filter(p=>p.group===g))}</div>`).join('');}
 function filters(){return `<div class="aa-filters"><label><span class="sr-only">搜索题目</span><input id="aa-search" placeholder="搜索题号、标题、标签…" value="${esc(state.search)}"></label><label><span class="sr-only">平台</span><select id="aa-platform"><option value="all">全部平台</option>${allPlatforms().map(p=>`<option value="${esc(p.id)}" ${state.platform===p.id?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><label><span class="sr-only">状态</span><select id="aa-status"><option value="all" ${state.status==='all'?'selected':''}>全部状态</option>${Object.keys(statusLabel).map(k=>`<option value="${k}" ${state.status===k?'selected':''}>${statusLabel[k]}</option>`).join('')}</select></label><label><span class="sr-only">排序</span><select id="aa-sort"><option value="recent" ${state.sort==='recent'?'selected':''}>最新记录</option><option value="hard" ${state.sort==='hard'?'selected':''}>难度从高到低</option><option value="easy" ${state.sort==='easy'?'selected':''}>难度从低到高</option></select></label></div>`;}
 function problems(){let ps=records();if(state.platform!=='all')ps=ps.filter(p=>p.platform===state.platform);if(state.status!=='all')ps=ps.filter(p=>p.status===state.status);if(state.search){const q=state.search.toLowerCase();ps=ps.filter(p=>[p.id,p.title,p.notes,p.platform,...(p.tags||[])].some(v=>String(v||'').toLowerCase().includes(q)));}if(state.sort==='hard')ps.sort((a,b)=>(b.rating??-1)-(a.rating??-1));else if(state.sort==='easy')ps.sort((a,b)=>(a.rating??99999)-(b.rating??99999));else ps.sort((a,b)=>(b.accepted_at||b.updated_at||'').localeCompare(a.accepted_at||a.updated_at||''));const loaded=ps.slice(0,state.page*state.limit);return `${viewHeader(state.platform==='all'?'全部题目':platform(state.platform).name+' · 题目',`共 ${ps.length} 条记录（本地归档不等于 AC）`,`<button class="aa-text-button" id="aa-csv-export">导出 CSV ↓</button>`) }${filters()}<div class="aa-table-wrapper">${problemTable(loaded)}<div class="aa-table-bottom"><span>显示 ${loaded.length} / ${ps.length} 条记录</span>${loaded.length<ps.length?'<button class="aa-btn" id="aa-more">加载更多</button>':''}</div></div><div class="aa-hint">网页为只读展示。可修改仓库 data/manual.csv，或从本地 AlgoArchive 导出记录；不需要在网页输入任何 OJ 密码。</div>`;}
 function contestsPage(){const data=contests();return `${viewHeader('完整比赛',`共 ${data.length} 场 · AlgoArchive 比赛归档与公开 Rated 记录统一查看`)}`+(data.length?`<div class="aa-contests">${data.map(c=>`<div class="aa-contest"><div><span class="aa-meta">${badge(c.platform)} · ${dt(c.date)}</span><h3><a href="${url(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.title||c.id||'未命名比赛')}</a></h3>${c.notes?`<p>${esc(c.notes)}</p>`:''}</div><div class="aa-contest-stats">${c.rank!=null?`<span>排名 <b>${esc(c.rank)}</b></span>`:''}${c.solved!=null?`<span>解出 <b>${esc(c.solved)}</b></span>`:''}${c.delta!=null?`<span>Rating <b class="${c.delta>=0?'aa-plus':'aa-minus'}">${c.delta>0?'+':''}${esc(c.delta)}</b></span>`:''}</div></div>`).join('')}</div>`:empty('暂无比赛。可在原 AlgoArchive 中归档比赛或录入 data/contests.csv。'));
 }
 function algorithmsPage(){const algorithms=state.local?.algorithms||[];const snippets=state.local?.snippets||[];const links=state.local?.links||[];const ps=records();return `${(state.blog?.templates||[]).map(t=>'<article class="aa-native-template">'+t.html+'</article>').join('')}${viewHeader('模板',`已公开 ${algorithms.length+(state.blog?.templates||[]).length} 项算法模板`)}`+(algorithms.length?`<div class="aa-algos">${algorithms.map(a=>{
   const sn=snippets.filter(s=>s.algorithm_id===a.id),li=links.filter(l=>l.algorithm_id===a.id),pro=ps.filter(p=>p.algorithm_id===a.id);
   return `<details class="aa-algo"><summary><span class="aa-algo-symbol">{ }</span><span><b>${esc(a.name)}</b><small>${esc(a.category||'未分类')} · ${sn.length} 份代码 · ${pro.length} 道题</small></span><i class="fas fa-chevron-down"></i></summary><div class="aa-algo-body">${a.description?`<p class="aa-algo-desc">${esc(a.description)}</p>`:''}${sn.map(s=>`<div class="aa-snippet"><b>${esc(s.title)}</b><small>${esc(s.language)}</small>${s.code?`<pre><code>${esc(s.code)}</code></pre>`:'<p class="aa-dim">本次未公开源代码。</p>'}</div>`).join('')}${pro.length?`<h4>关联题目</h4>${pro.slice(0,30).map(p=>`<a class="aa-chip-link" href="${url(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title||p.id)}</a>`).join('')}`:''}${li.length?`<h4>参考链接</h4>${li.map(l=>`<a class="aa-chip-link" href="${url(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.title||l.url)} ↗</a>`).join('')}`:''}</div></details>`;}).join('')}</div>`:empty('还没有公开的算法模板。'));
 }
 function setActive(){for(const b of document.querySelectorAll('#aa-root [data-aa-view]')){const yes=b.dataset.aaView===state.view&&(b.dataset.aaOj===undefined||b.dataset.aaOj===state.platform);b.classList.toggle('active',yes);}}
 function render(){const root=$('aa-content');if(!root)return;root.innerHTML=({home,problems,contests:()=>AAWorkspaces.calendar(state),editorials:()=>AAWorkspaces.editorial(state),practice:()=>AAWorkspaces.practice(state),multischool:()=>AAWorkspaces.multischool(state),algorithms:algorithmsPage}[state.view]||home)();setActive();}
 function change(view,oj){state.view=view==='analysis'?'home':view;state.page=1;if(oj!==undefined){state.platform=oj;if(view==='analysis')state.analysisPlatform=oj;}render();try{history.replaceState(null,'','#aa-'+view+(view==='problems'?'--'+state.platform:''));}catch(_){}}
 function exportCSV(){const fields=['platform','id','title','url','status','rating','level','tags','accepted_at','notes'];const cell=x=>'"'+String(x??'').replace(/"/g,'""')+'"';const csv='\ufeff'+fields.join(',')+'\r\n'+records().map(p=>fields.map(k=>cell(k==='tags'?(p.tags||[]).join(';'):p[k])).join(',')).join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'}),a=document.createElement('a'),ref=URL.createObjectURL(blob);a.href=ref;a.download='lostin-algorithm-archive.csv';a.click();setTimeout(()=>URL.revokeObjectURL(ref),3000);}
 function dayDetail(day){
   const list=records().filter(p=>p.status==='AC'&&(state.analysisPlatform==='all'||p.platform===state.analysisPlatform)&&AAAnalytics.dayKey(p.first_accepted_at||(p.source==='manual'?p.accepted_at:null))===day);
   const target=$('aa-day-detail');
   if(target){target.innerHTML=viewHeader(day+' · 首次通过',list.length+' 道题目')+problemTable(list.map(p=>({...p,accepted_at:p.first_accepted_at||p.accepted_at})));target.scrollIntoView?.({block:'nearest',behavior:'smooth'});}
 }
 function attach(root){
   root.addEventListener('click',e=>{
     const date=e.target.closest('[data-aa-day]');if(date){dayDetail(date.dataset.aaDay);return;}
     const tag=e.target.closest('[data-aa-tag]');if(tag){state.search=tag.dataset.aaTag;change('problems',state.analysisPlatform);return;}
     const nav=e.target.closest('[data-aa-view]');if(nav){change(nav.dataset.aaView,nav.dataset.aaOj);return;}
     if(e.target.closest('#aa-refresh')){Promise.all([refreshData(true),refreshCatalog(true)]);return;}
     const pagination=e.target.closest('[data-aa-page]');if(pagination&&!pagination.disabled){state[pagination.dataset.aaPage]=Math.max(1,Number(pagination.dataset.page));render();return;}
     const mode=e.target.closest('[data-aa-event-mode]');if(mode){state.eventMode=mode.dataset.aaEventMode;state.eventPage=1;render();return;}
     if(e.target.closest('#aa-more')){state.page++;render();return;}
     if(e.target.closest('#aa-csv-export'))exportCSV();
   });
   root.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('[data-aa-day]')){e.preventDefault();dayDetail(e.target.dataset.aaDay);}});
   root.addEventListener('input',e=>{if(e.target.id==='aa-practice-search'){const pos=e.target.selectionStart;state.practiceSearch=e.target.value;state.practicePage=1;render();$('aa-practice-search')?.focus();$('aa-practice-search')?.setSelectionRange(pos,pos);return;}if(e.target.id==='aa-search'){const position=e.target.selectionStart;state.search=e.target.value;state.page=1;render();const i=$('aa-search');i?.focus();i?.setSelectionRange(position,position);}});
   root.addEventListener('change',e=>{
     const v=e.target.value;
     switch(e.target.id){
       case'aa-practice-year':state.practiceYear=v;state.practicePage=1;break;
       case'aa-practice-series':state.practiceSeries=v;state.practicePage=1;break;
       case'aa-practice-stage':state.practiceStage=v;state.practicePage=1;break;
       case'aa-event-platform':state.eventPlatform=v;state.eventPage=1;break;
       case'aa-analysis-platform':state.analysisPlatform=v;break;
       case'aa-analysis-year':state.analysisYear=v;break;
       case'aa-platform':state.platform=v;break;
       case'aa-status':state.status=v;break;
       case'aa-sort':state.sort=v;break;
       default:return;
     }
     state.page=1;render();$(e.target.id)?.focus();
   });
 }
 async function readData(path, schema) {
   const response = await fetch(path, {cache:'no-cache', signal:AbortSignal.timeout(15000)});
   if (!response.ok) throw Error(path + ' HTTP ' + response.status);
   const data = await response.json();
   const arrays = schema === 2 ? ['platforms','problems','contests'] : ['problems','contests','algorithms','snippets','links'];
   if (data?.schema !== schema || arrays.some(key => !Array.isArray(data[key]))) throw Error(path + ' 数据格式不正确');
   return data;
 }
 let timer=null,catalogTimer=null;
 function updateRefreshButton(){const b=$('aa-refresh');if(!b)return;const fetching=state.refreshing||state.catalogRefreshing,busy=fetching||state.public?.live?.refreshing||state.catalog?.live?.refreshing;b.disabled=!!fetching;b.classList.toggle('is-loading',!!busy);b.setAttribute('aria-busy',String(!!busy));}
 function syncDisplay(liveFailed=false){
   const updated=allPlatforms().map(p=>p.last_ok||'').sort().pop();
   const stamp=updated?new Date(updated).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚无成功同步';
   const isUpdating=state.public?.live?.refreshing;
   $('aa-sync').textContent=' · '+(state.liveEndpoint?(isUpdating?'接口更新中 · 上次成功：':'访问时刷新 · 上次成功：'):'静态快照 · 上次成功：')+stamp;
   const notices=[];
   if(liveFailed)notices.push('实时接口暂时不可用，保留缓存记录。请稍后点击刷新。');
   const limited=allPlatforms().filter(p=>['error','blocked','partial'].includes(p.sync_status)).map(p=>p.name);if(limited.length)notices.push(limited.join('、')+' 暂时无法完整同步，其余平台正常更新。');
   $('aa-notice').hidden=!notices.length;$('aa-notice').textContent=notices.join(' ');
 }
 async function refreshData(manual=false){
   if(state.refreshing||!$('aa-root'))return;
   state.refreshing=true;
   updateRefreshButton();
   try{
     const data=await readData(state.liveEndpoint||'/algo/data.json',2);
     const changed=data.generated_at!==state.public?.generated_at;
     state.public=data;syncDisplay();
     if(changed||manual){
       const active=document.activeElement,id=active?.id,position=active?.selectionStart;
       render();if(id){$(id)?.focus();if(position!=null)$(id)?.setSelectionRange?.(position,position);}
     }
   }catch(_){syncDisplay(true);}
   finally{
     state.refreshing=false;
     updateRefreshButton();
     clearTimeout(timer);timer=setTimeout(()=>{if(!document.hidden)refreshData();else timer=setTimeout(()=>refreshData(),60000);},state.public?.live?.refreshing?5000:60000);
   }
 }
 async function readJSON(path){const r=await fetch(path,{cache:'no-cache',signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error('Data unavailable');return r.json();}
 async function refreshCatalog(manual=false){
   if(state.catalogRefreshing)return;state.catalogRefreshing=true;updateRefreshButton();
   try{const d=await readJSON(state.catalogEndpoint||'/algo/catalog.json');if(d.schema!==1||!Array.isArray(d.events)||!Array.isArray(d.practice?.items))throw Error('Invalid catalogue');state.catalog=d;state.catalogError=false;if(['contests','practice','multischool'].includes(state.view)||manual)render();}
   catch(_){state.catalogError=true;}
   finally{state.catalogRefreshing=false;updateRefreshButton();clearTimeout(catalogTimer);catalogTimer=setTimeout(()=>refreshCatalog(),state.catalog?.live?.refreshing?5000:60000);}
 }
 async function start(){
   const root=$('aa-root');if(!root||root.dataset.aaInitialized==='1')return;
   root.dataset.aaInitialized='1';attach(root);
   const [a,b,c,d]=await Promise.allSettled([readData('/algo/data.json',2),readData('/algo/archive.json',1),readJSON('/algo/blog.json'),readJSON('/algo/catalog.json')]);
   state.public=a.status==='fulfilled'?a.value:{platforms:[],problems:[],contests:[],ratings:{}};
   state.local=b.status==='fulfilled'?b.value:{problems:[],contests:[],algorithms:[],snippets:[],links:[]};
   state.blog=c.status==='fulfilled'&&Array.isArray(c.value.posts)?c.value:{posts:[],templates:[]};
   state.catalog=d.status==='fulfilled'&&Array.isArray(d.value.events)?d.value:{schema:1,events:[],practice:{items:[]},sources:{}};
   if(location.hash.startsWith('#aa-')){const matched=location.hash.match(/^#aa-(home|analysis|problems|contests|algorithms|editorials|practice|multischool)(?:--([a-z0-9_-]+))?$/);if(matched){state.view=matched[1]==='analysis'?'home':matched[1];state.platform=matched[2]||'all';}}
   render();syncDisplay();
   if(a.status!=='fulfilled'||b.status!=='fulfilled'){$('aa-notice').hidden=false;$('aa-notice').textContent=(a.status!=='fulfilled'?'OJ 数据暂时无法读取，请稍后刷新。':'')+(b.status!=='fulfilled'?'本地档案暂时无法读取，请稍后刷新。':'');}
   try{
     const response=await fetch('/algo/live.json',{cache:'no-cache',signal:AbortSignal.timeout(10000)}),config=await response.json();
     if(config.catalog_endpoint){const e=new URL(config.catalog_endpoint,location.href);if(e.protocol==='https:'||['localhost','127.0.0.1'].includes(e.hostname))state.catalogEndpoint=e.href;}
     if(config.endpoint){const endpoint=new URL(config.endpoint,location.href);if(endpoint.protocol==='https:'||['localhost','127.0.0.1'].includes(endpoint.hostname))state.liveEndpoint=endpoint.href;}
   }catch(_){}
   if(state.liveEndpoint)refreshData();else timer=setTimeout(()=>refreshData(),60000);
   if(state.catalogEndpoint)refreshCatalog();
 }
 window.addEventListener('pagehide',()=>{clearTimeout(timer);clearTimeout(catalogTimer);});
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
 // Butterfly may use PJAX; re-initialize after its content replacement.
 document.addEventListener('pjax:complete',start);
})();
