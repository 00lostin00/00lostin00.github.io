/* Native Butterfly workspaces. Data adapters are independent of upstream UI code. */
(() => {
 'use strict';
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const link=v=>{try{const u=new URL(v,location.origin);return ['https:','http:'].includes(u.protocol)?esc(u.href):'#';}catch(_){return '#';}};
 const host=v=>{try{return new URL(v,location.origin).hostname;}catch(_){return '打开链接';}};
 const names={codeforces:'Codeforces',atcoder:'AtCoder',luogu:'洛谷',nowcoder:'牛客'};
 const stages={network:'网络赛',regional:'区域赛',invitational:'邀请赛',provincial:'省赛'};
 const stamp=v=>{const d=new Date(v);return Number.isFinite(d.getTime())?d.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'时间待公布';};
 const heading=(title,note)=>`<div class="aa-section-head"><div><h2>${esc(title)}</h2><p>${esc(note)}</p></div></div>`;
 const empty=text=>`<div class="aa-empty"><i class="fas fa-inbox"></i><p>${esc(text)}</p></div>`;
 function pager(page,count,size,key){const pages=Math.max(1,Math.ceil(count/size));return `<div class="aa-pagination"><span>共 ${count} 项 · 第 ${page}/${pages} 页</span><div><button data-aa-page="${key}" data-page="${page-1}" ${page<=1?'disabled':''}>上一页</button><button data-aa-page="${key}" data-page="${page+1}" ${page>=pages?'disabled':''}>下一页</button></div></div>`;}
 function field(id,label,options,value){return `<label>${esc(label)}<select id="${id}">${options.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;}
 function editorial(state){
  const posts=state.blog?.posts||[],size=6,page=Math.min(state.blogPage,Math.max(1,Math.ceil(posts.length/size)));
  return heading('题解','自己的比赛题解，按发布时间整理')+(posts.length?`<div class="aa-editorials">${posts.slice((page-1)*size,page*size).map(p=>`<article class="aa-editorial"><time>${esc(String(p.date||'').slice(0,10))}</time><h3><a href="${link(p.url)}">${esc(p.title)}</a></h3><p>${esc(p.excerpt)}</p><a class="aa-editorial-read" href="${link(p.url)}">阅读全文 <i class="fas fa-angle-right"></i></a></article>`).join('')}</div>`:empty('还没有公开题解。'))+pager(page,posts.length,size,'blogPage');
 }
 function linkText(text){
  const parts=String(text||'').split(/(https?:\/\/[^\s<>，；。"']+)/g);
  return parts.map(p=>/^https?:\/\//.test(p)?`<a href="${link(p)}" target="_blank" rel="noopener noreferrer">${esc(p)}</a>`:esc(p)).join('');
 }
 function practice(state){
  const catalog=state.catalog||{},all=catalog.practice?.items||[];
  const years=[...new Set(all.map(x=>String(x.year)).filter(Boolean))].sort().reverse();
  let items=all.filter(x=>(state.practiceYear==='all'||String(x.year)===state.practiceYear)&&(state.practiceSeries==='all'||x.series===state.practiceSeries)&&(state.practiceStage==='all'||x.stage===state.practiceStage));
  if(state.practiceSearch){const q=state.practiceSearch.toLowerCase();items=items.filter(x=>[x.name,x.official_name,x.organizer,x.notes].some(v=>String(v||'').toLowerCase().includes(q)));}
  const size=12,page=Math.min(state.practicePage,Math.max(1,Math.ceil(items.length/size))),source=catalog.sources?.practice;
  return heading('补题链接','按 AlgoWiki 的年份、ICPC / CCPC 和比赛类别整理')+`<div class="aa-catalog-filters">${field('aa-practice-year','年份',[['all','全部年份'],...years.map(y=>[y,y])],state.practiceYear)}${field('aa-practice-series','系列',[['all','全部'],['icpc','ICPC'],['ccpc','CCPC']],state.practiceSeries)}${field('aa-practice-stage','分类',[['all','全部分类'],...Object.entries(stages)],state.practiceStage)}<label class="aa-catalog-search">搜索<input id="aa-practice-search" value="${esc(state.practiceSearch)}" placeholder="比赛名称、承办学校…"></label></div>`+
   (items.length?`<div class="aa-practice-list">${items.slice((page-1)*size,page*size).map(x=>`<article class="aa-practice-entry"><div class="aa-practice-meta"><span>${esc(x.year)}</span><span>${esc(x.series?.toUpperCase())}</span><span>${esc(stages[x.stage]||x.stage)}</span>${x.date?`<time>${esc(x.date)}</time>`:''}</div><h3>${esc(x.name)}</h3>${x.organizer?`<p class="aa-practice-school">${esc(x.organizer)}</p>`:''}<div class="aa-practice-links">${(x.links||[]).map(l=>`<a href="${link(l.url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-external-link-alt"></i> ${esc(l.label||host(l.url))}</a>`).join('')||'<span class="aa-dim">来源暂未提供补题链接</span>'}</div>${x.notes?`<details><summary>备注与更多链接</summary><p>${linkText(x.notes)}</p></details>`:''}</article>`).join('')}</div>`:empty(source?.error?'来源暂时无法更新，已保留可用缓存。':'当前分类暂无补题链接。'))+pager(page,items.length,size,'practicePage')+
   `<p class="aa-source-credit">来源：<a href="https://www.algowiki.cn/competitions?tab=practice" target="_blank" rel="noopener noreferrer">AlgoWiki 补题链接</a> · ${source?.last_ok?'最近读取 '+stamp(source.last_ok):'等待首次同步'}${source?.error?' · 更新受限，保留缓存':''}</p>`;
 }
 function countdown(event,now){const start=Date.parse(event.start),end=Date.parse(event.end);if(now>=start&&now<end)return '进行中';if(now>=end)return '已结束';const minutes=Math.max(0,Math.ceil((start-now)/60000)),d=Math.floor(minutes/1440),h=Math.floor(minutes%1440/60),m=minutes%60;return (d?d+' 天 ':'')+(h?h+' 小时 ':'')+(!d?m+' 分钟 ':'')+'后开始';}
 function calendar(state){
  const now=Date.now();let events=(state.catalog?.events||[]).filter(x=>state.eventPlatform==='all'||x.platform===state.eventPlatform);
  events=events.filter(x=>state.eventMode==='recent'?Date.parse(x.end)<=now:state.eventMode==='live'?Date.parse(x.start)<=now&&Date.parse(x.end)>now:Date.parse(x.start)>now);
  events.sort((a,b)=>state.eventMode==='recent'?Date.parse(b.end)-Date.parse(a.end):Date.parse(a.start)-Date.parse(b.start));
  const size=12,page=Math.min(state.eventPage,Math.max(1,Math.ceil(events.length/size)));
  return heading('赛事中心','Codeforces / AtCoder / 洛谷 / 牛客 · 北京时间')+`<div class="aa-calendar-toolbar"><div class="aa-view-switch">${[['upcoming','即将开始'],['live','进行中'],['recent','最近结束']].map(([v,t])=>`<button data-aa-event-mode="${v}" class="${state.eventMode===v?'active':''}">${t}</button>`).join('')}</div>${field('aa-event-platform','平台',[['all','全部平台'],...Object.entries(names)],state.eventPlatform)}</div>`+
   (events.length?`<div class="aa-events-grid">${events.slice((page-1)*size,page*size).map(x=>`<article class="aa-event-card"><div class="aa-event-platform"><i class="aa-event-dot aa-platform-${esc(x.platform)}"></i><b>${esc(names[x.platform]||x.platform)}</b>${x.kind?`<span>${esc(x.kind)}</span>`:''}</div><h3><a href="${link(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.title)} <i class="fas fa-external-link-alt"></i></a></h3><div class="aa-event-times"><span><i class="far fa-clock"></i> ${Math.floor(x.duration/3600)} 小时${x.duration%3600?' '+Math.round(x.duration%3600/60)+' 分钟':''}</span><time datetime="${esc(x.start)}">${stamp(x.start)}</time></div><span class="aa-event-countdown">${countdown(x,now)}</span>${x.fallback?'<small class="aa-event-cache">赛历来源缓存</small>':''}</article>`).join('')}</div>`:empty(state.catalog?.live?.refreshing?'正在更新各平台赛历…':'当前条件下暂无赛事。'))+pager(page,events.length,size,'eventPage')+
   `<div class="aa-calendar-source">${Object.entries(names).map(([id,name])=>{const s=state.catalog?.sources?.[id];return `<span title="${esc(s?.last_ok?stamp(s.last_ok):'尚未成功读取')}">${name} · ${s?.error?'保留缓存':s?.last_ok?'已更新':'等待同步'}</span>`;}).join('')}</div>`;
 }
 function matrix(contests,known,isAC){
  return `<div class="aa-matrix-scroll"><table class="aa-matrix"><thead><tr><th scope="col">比赛</th><th scope="col">题目进度</th><th scope="col">通过</th></tr></thead><tbody>${contests.map(c=>{
   const ps=c.problems||[],ready=known&&!!c.last_ok,solved=ps.filter(p=>isAC(p,c)).length;
   return `<tr><th scope="row"><a href="${link(c.url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-link"></i> ${esc(c.title)}</a>${c.progress?.is_team?'<small>含关联队伍记录</small>':''}${c.error?'<small>更新受限，保留已有记录</small>':''}</th><td><div class="aa-problem-blocks">${ps.map(p=>{const ac=ready&&isAC(p,c);return `<a class="aa-problem-block ${ac?'is-ac':''}" href="${link(p.url)}" target="_blank" rel="noopener noreferrer" title="${esc(p.index+' · '+(p.title||p.id)+' · '+(ac?'已通过':ready?'暂无该题 AC 记录':'账号记录尚未同步'))}" aria-label="${esc(p.index+' · '+(p.title||p.id)+' · '+(ac?'已通过':ready?'暂无 AC 记录':'待同步'))}">${esc(p.index)}</a>`;}).join('')||'<span class="aa-dim">题单暂不可用</span>'}</div></td><td class="aa-matrix-total">${ready&&ps.length?'<b class="'+(solved?'has-ac':'')+'">'+solved+'</b> / '+ps.length:'—'}</td></tr>`;
  }).join('')}</tbody></table></div>`;
 }
 function multischool(state){
  const items=state.catalog?.multischool||[],nc=items.find(x=>x.id==='nowcoder'),hdu=items.find(x=>x.id==='hdu');
  const own=state.public?.platforms?.find(x=>x.id==='nowcoder');
  const known=!!(own?.last_ok&&String(own.handle)===String(nc?.account));
  const passed=new Set((state.public?.problems||[]).filter(p=>p.platform==='nowcoder'&&p.status==='AC').map(p=>String(p.id)));
  const contests=(nc?.contests||[]).map(c=>({...c,last_ok:c.progress?.account===nc?.account?c.progress?.last_ok:null,error:[c.error,c.progress?.error].filter(Boolean).join(' ')})),years=[...new Set(contests.map(c=>c.year))].sort((a,b)=>b-a);
  const tables=years.map(year=>`<section class="aa-multi-year"><div class="aa-multi-year-head"><h3>${year} 牛客暑期多校</h3><span>${contests.filter(c=>c.year===year).length} 场</span></div>${matrix(contests.filter(c=>c.year===year),!!nc?.account,(p,c)=>(c.progress?.accepted||[]).some(a=>String(a.id)===String(p.id))||(known&&passed.has(String(p.id))))}</section>`).join('');
  const seasons=hdu?.seasons||[{name:'2026 暑期多校'},{name:'2026 春季多校'},{name:'2025 暑期多校'}];
  return heading('多校训练','逐场查看题目进度 · 绿色表示当前账号已通过')+`<div class="aa-multi-account"><i class="fas fa-user-check"></i><span>牛客 ${esc(nc?.account||'账号待配置')} · ${known?'已接入比赛内提交与关联队伍'+(own.sync_status==='ok'?'':'，当前使用缓存'):'等待账号记录同步'}</span><span class="aa-multi-key"><i></i> 暂无 AC 记录 <i class="is-ac"></i> 已通过</span></div>`+(tables||empty('牛客近三年的多校题单正在同步。'))+
  `<p class="aa-chart-note">按个人账号查询比赛提交，包含牛客自动关联的参赛队伍。队伍进度单独展示，不混入个人 AC 总数。</p>`+
  seasons.map(s=>`<section class="aa-multi-year"><div class="aa-multi-year-head"><h3>${esc(s.name)}</h3><span>${(s.contests||[]).length} 场${s.last_ok?' · '+stamp(s.last_ok):''}</span></div>${s.contests?.length?matrix(s.contests,!!s.last_ok,p=>p.status==='AC'):`<div class="aa-hdu-season"><i class="fas fa-graduation-cap"></i><span>${s.account_configured?'正在读取授权账号记录，稍后刷新':'比赛入口与登录账号待配置'}</span></div>`}${['error','partial','cached'].includes(s.sync_status)?'<p class="aa-chart-note">'+(s.sync_status==='cached'?'当前为已公开的记录快照，在线接口可更新。':'该训练季暂时无法完整更新，保留已有记录。')+'</p>':''}</section>`).join('');
 }
 globalThis.AAWorkspaces={editorial,practice,calendar,multischool};
})();
