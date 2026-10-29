/* Theme-native SVG charts. No external chart service or synthetic records. */
(() => {
  'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const colors=['#ef7e79','#e968a9','#b57ae5','#8b8ee8','#55b9db','#59c8b6','#6cbd80','#b8d96b','#e7ca62','#c89d79','#a5a9b2'];
  const ojColors={codeforces:'#638ce2',atcoder:'#50a4b3',nowcoder:'#db9a58',luogu:'#54ad88',qoj:'#9d82ce'};
  const color=id=>ojColors[id]||'#87959e';
  function sources(platforms){
    const labels={ok:'已同步',partial:'历史不完整',error:'同步受限',blocked:'访问受限',not_configured:'未配置',offline:'离线缓存',manual:'手动记录'};
    return `<div class="aa-source-status">${platforms.filter(p=>['codeforces','atcoder','nowcoder','luogu','qoj'].includes(p.id)).map(p=>{
      const last=p.last_ok?new Date(p.last_ok).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚无成功同步';
      return `<div><b>${esc(p.name)}</b><span class="${p.sync_status==='ok'?'aa-good':'aa-warn'}">${labels[p.sync_status]||'等待同步'}</span><small>${esc(p.handle||'未设置账号')} · ${esc(last)}</small></div>`;
    }).join('')}</div><p class="aa-chart-note">访问时请求接口；共享缓存最短 60 秒。每个平台受上游更新速度和访问限制影响，以各自的成功时间为准。</p>`;
  }
  function heatmap(a){
    const offset=a.days[0]?.weekday||0,cell=13,gap=3;
    const columns=Math.ceil((a.days.length+offset)/7),w=columns*(cell+gap)+44;
    const max=Math.max(1,...a.days.map(d=>d.count)),months=[];
    const boxes=a.days.map((d,i)=>{
      const x=35+Math.floor((i+offset)/7)*(cell+gap),y=25+d.weekday*(cell+gap);
      if(d.day.endsWith('-01')||i===0)months.push(`<text x="${x}" y="14">${Number(d.day.slice(5,7))}月</text>`);
      const level=d.count?Math.min(4,1+Math.floor((d.count-1)*4/max)):0;
      return `<g role="button" tabindex="0" data-aa-day="${d.day}" aria-label="${d.day} 首次通过 ${d.count} 题"><title>${d.day} · 首次通过 ${d.count} 题</title><rect class="aa-heat-${level}" x="${x}" y="${y}" width="${cell}" height="${cell}" rx="2"/></g>`;
    }).join('');
    return `<div class="aa-heat-scroll"><svg class="aa-heatmap" viewBox="0 0 ${w} 144" style="min-width:${Math.min(w,650)}px" role="group" aria-label="${a.year==='rolling'?'最近365天':a.year+'年'}每日首次通过热力图">${months.join('')}<text x="0" y="51">周一</text><text x="0" y="83">周三</text><text x="0" y="115">周五</text>${boxes}</svg></div><div class="aa-heat-key"><span>少</span>${[0,1,2,3,4].map(n=>`<i class="aa-heat-${n}"></i>`).join('')}<span>多 · 点击日期查看题目</span></div>`;
  }
  function donut(a){
    if(!a.tags.length)return '<p class="aa-chart-empty">当前范围暂无标签数据。尚未提供标签的平台不会被推测分类。</p>';
    const total=a.tags.reduce((s,t)=>s+t.count,0);let cursor=0;
    const rings=a.tags.map((t,i)=>{
      const share=t.count/total*100,start=cursor;cursor+=share;
      return `<circle cx="100" cy="100" r="70" fill="none" stroke="${colors[i%colors.length]}" stroke-width="30" pathLength="100" stroke-dasharray="${share} ${100-share}" stroke-dashoffset="${-start}" transform="rotate(-90 100 100)"><title>${esc(t.label)} · ${t.count} 题</title></circle>`;
    }).join('');
    return `<div class="aa-tag-chart"><svg viewBox="0 0 200 200" role="img" aria-label="算法标签分布">${rings}<text x="100" y="98" text-anchor="middle" class="aa-donut-number">${a.tagged}</text><text x="100" y="120" text-anchor="middle">有标签题目</text></svg><div class="aa-tag-legend">${a.tags.map((t,i)=>`<button type="button" data-aa-tag="${esc(t.label)}"><i style="background:${colors[i%colors.length]}"></i><span>${esc(t.label)}</span><b>${t.count}</b></button>`).join('')}</div></div><p class="aa-chart-note">标签覆盖 ${a.tagged}/${a.periodTotal} 题；一道题可有多个标签，扇区表示标签出现次数。</p>`;
  }
  function difficulty(a){
    const max=Math.max(1,...a.difficulty.map(d=>d.count));
    return a.difficulty.length?`<div class="aa-bar-list">${a.difficulty.map(d=>`<div><span>${esc(d.label)}</span><i><b style="width:${d.count/max*100}%"></b></i><strong>${d.count}</strong></div>`).join('')}</div><p class="aa-chart-note">CF 官方 Rating 与 AT 社区模型估计值分别分桶，尺度不直接比较；AT 原始估计可能为负。其他平台保留原生等级，缺失值单列。</p>`:'<p class="aa-chart-empty">当前范围暂无首次通过记录。</p>';
  }
  function monthly(a,platforms){
    const actual=new Map(a.monthly.map(m=>[m.month,m.platforms]));
    const today=new Date(a.today+'T00:00:00Z');
    const end=a.year==='rolling'?new Date(Date.UTC(today.getUTCFullYear(),today.getUTCMonth(),1)):new Date(Date.UTC(Number(a.year),Number(a.year)===today.getUTCFullYear()?today.getUTCMonth():11,1));
    const length=a.year==='rolling'?12:end.getUTCMonth()+1;
    const months=Array.from({length},(_,i)=>{const date=new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-length+1+i,1)),month=date.toISOString().slice(0,7);return {month,platforms:actual.get(month)||{}};});
    const highest=Math.max(1,...months.map(m=>Object.values(m.platforms).reduce((n,x)=>n+x,0)));
    const magnitude=10**Math.floor(Math.log10(highest/4)),step=[1,2,5,10].map(n=>n*magnitude).find(n=>n>=highest/4)||1,max=Math.ceil(highest/step)*step;
    const width=760,height=230,left=42,top=26,plotHeight=164,plotWidth=700,column=plotWidth/months.length,bar=Math.min(34,column*.56);
    const grid=Array.from({length:Math.round(max/step)+1},(_,i)=>{const n=i*step,y=top+plotHeight-n/max*plotHeight;return `<line x1="${left}" x2="${left+plotWidth}" y1="${y}" y2="${y}" class="aa-month-grid"/><text x="${left-10}" y="${y+4}" text-anchor="end">${n}</text>`;}).join('');
    const bars=months.map((m,i)=>{const x=left+(i+.5)*column-bar/2,total=Object.values(m.platforms).reduce((n,v)=>n+v,0),h=total/max*plotHeight,y=top+plotHeight-h;let cursor=top+plotHeight;const parts=Object.entries(m.platforms).map(([id,count])=>{const hh=count/max*plotHeight;cursor-=hh;return `<rect x="${x}" y="${cursor}" width="${bar}" height="${hh}" fill="${color(id)}"/>`;}).join('');return `<g><title>${m.month} · 新增 ${total} 题${Object.entries(m.platforms).map(([id,n])=>' · '+(platforms.find(p=>p.id===id)?.name||id)+' '+n).join('')}</title><defs><clipPath id="aa-month-${i}"><rect x="${x}" y="${y}" width="${bar}" height="${h}" rx="5"/></clipPath></defs><g clip-path="url(#aa-month-${i})">${parts}</g><text x="${x+bar/2}" y="${Math.max(14,y-8)}" text-anchor="middle" class="aa-month-value">${total}</text><text x="${x+bar/2}" y="${top+plotHeight+23}" text-anchor="middle">${m.month.slice(2)}</text></g>`;}).join('');
    return `<div class="aa-month-chart-scroll"><svg viewBox="0 0 ${width} ${height}" class="aa-month-svg" role="img" aria-label="月度新增通过，按平台分组">${grid}${bars}</svg></div><div class="aa-chart-oj-legend">${platforms.filter(p=>a.selected.some(s=>s.platform===p.id)).map(p=>`<span><i style="background:${color(p.id)}"></i>${esc(p.name)}</span>`).join('')}</div>`;
  }
  function render({problems,platforms,tagSync,platform='all',year='rolling',today}){
    const a=AAAnalytics.analyze(problems,{platform,year,today});
    const difference=a.last30-a.previous30;
    const peak=[...a.days].sort((x,y)=>y.count-x.count)[0];
    const cf=a.selected.filter(p=>p.platform==='codeforces'&&p.rating!=null).map(p=>Number(p.rating)).filter(Number.isFinite).sort((x,y)=>x-y);
    const median=cf.length?(cf[Math.floor((cf.length-1)/2)]+cf[Math.floor(cf.length/2)])/2:null;
    const reading=`<section class="aa-analysis-reading"><h3>训练观察</h3><ul><li>近 30 天新增通过 ${a.last30} 题，前 30 天为 ${a.previous30} 题，变化 ${difference>=0?'+':''}${difference} 题。</li><li>${a.periodTotal?`所选范围活跃 ${a.activeDays} 天，平均每个活跃日 ${(a.periodTotal/Math.max(1,a.activeDays)).toFixed(1)} 题；单日最高 ${peak.count} 题（${peak.day}）。`:'所选范围暂无有日期的首次 AC 记录。'}</li><li>${a.tags.length?`记录最多的标签是 ${a.tags.slice(0,3).map(t=>esc(t.label)+'（'+t.count+'）').join('、')}。`:'当前范围尚无可用算法标签。'}标签分布反映已有训练内容，不等同于能力测评。</li>${median!=null?`<li>所选范围中 ${cf.length} 道已标定 CF 题的难度中位数为 ${median}；不与其他 OJ 的难度数值混算。</li>`:''}</ul></section>`;
    return `<section class="aa-insights" aria-label="跨平台训练分析"><div class="aa-analysis-head"><div><h2>训练分析</h2><p>北京时间 · 每题仅计首次 AC · 按 OJ + 题号去重</p></div><div class="aa-analysis-filters"><label>平台<select id="aa-analysis-platform"><option value="all">全部 OJ</option>${platforms.map(p=>`<option value="${esc(p.id)}" ${platform===p.id?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><label>年份<select id="aa-analysis-year"><option value="rolling" ${year==='rolling'?'selected':''}>最近 365 天</option>${a.years.map(y=>`<option value="${y}" ${year===y?'selected':''}>${y} 年</option>`).join('')}</select></label></div></div>
      ${sources(platforms)}<div class="aa-chart-block aa-training-calendar">${heatmap(a)}<div class="aa-training-totals"><div><b>${a.total}</b><span>已取得的累计通过题目</span><small>最长连续 ${a.longest} 天</small></div><div><b>${a.periodTotal}</b><span>${year==='rolling'?'近 365 天':'所选年份'}首次通过</span><small>活跃 ${a.activeDays} 天 · 最长连续 ${a.periodLongest} 天</small></div><div><b>${a.last30}</b><span>近 30 天首次通过</span><small>较前 30 天 ${difference>=0?'+':''}${difference} 题 · 当前连续 ${a.currentStreak} 天</small></div></div></div>
      ${a.unknown?`<p class="aa-chart-note">${a.unknown} 道已通过题目缺少可确认的首次 AC 日期，计入累计题数，但不填入日历。</p>`:''}
      <div class="aa-analysis-grid"><section class="aa-chart-block"><h3>算法标签分布</h3>${donut(a)}${tagSync?'<p class="aa-chart-note">标签来源已检查 '+tagSync.completed+'/'+tagSync.total+' 题 · 持续后台更新</p>':''}</section><section class="aa-chart-block"><h3>难度分布</h3>${difficulty(a)}</section></div>
      <section class="aa-chart-block aa-month-panel"><h3>月度新增通过</h3>${monthly(a,platforms)}</section>
      ${reading}<div id="aa-day-detail" class="aa-day-detail" aria-live="polite"></div></section>`;
  }
  globalThis.AAInsights={render};
})();
