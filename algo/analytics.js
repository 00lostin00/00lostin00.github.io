/* Pure analysis shared by the browser and regression tests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AAAnalytics = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const DAY = 86400000;
  const dateFormat = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai', year:'numeric',month:'2-digit',day:'2-digit'});
  function dayKey(value) {
    if (!value) return null;
    // Date-only imports already represent a local calendar day.
    if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
      const parsed=new Date(value+'T00:00:00Z');
      return Number.isFinite(parsed.getTime())&&parsed.toISOString().slice(0,10)===value?String(value):null;
    }
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return null;
    const p = Object.fromEntries(dateFormat.formatToParts(date).map(x=>[x.type,x.value]));
    return `${p.year}-${p.month}-${p.day}`;
  }
  const stamp = day => Date.parse(day+'T00:00:00Z');
  const fromStamp = value => new Date(value).toISOString().slice(0,10);
  function streak(days) {
    let longest=0,current=0,last=null;
    for (const day of [...new Set(days)].sort()) {
      const next=stamp(day);
      current=last!==null && next-last===DAY?current+1:1;
      longest=Math.max(longest,current); last=next;
    }
    return longest;
  }
  function analyze(problems, options={}) {
    const today=dayKey(options.today||new Date()), now=stamp(today), byId=new Map();
    for (const p of problems) {
      if (p.status!=='AC' || (options.platform && options.platform!=='all' && p.platform!==options.platform)) continue;
      const id=p.platform+':'+String(p.id).toLowerCase(), previous=byId.get(id);
      // Legacy caches without a verified first AC date are not silently treated as full history.
      const first=p.first_accepted_at || (p.source==='manual'||p.origin==='manual'?p.accepted_at:null);
      const day=dayKey(first);
      const item={...p,day};
      if (!previous || day && (!previous.day || day<previous.day)) byId.set(id,item);
    }
    const solved=[...byId.values()];
    const dated=solved.filter(p=>p.day && p.day<=today), unknown=solved.length-dated.length;
    const counts=new Map();
    for(const p of dated)counts.set(p.day,(counts.get(p.day)||0)+1);
    const currentYear=Number(today.slice(0,4));
    const historyYears=problems.map(p=>dayKey(p.first_accepted_at||(p.source==='manual'?p.accepted_at:null))).filter(Boolean).map(d=>Number(d.slice(0,4)));
    const firstYear=Math.min(currentYear,...historyYears);
    const years=Array.from({length:currentYear-firstYear+1},(_,i)=>String(currentYear-i));
    const year=options.year&&options.year!=='rolling'?String(options.year):'rolling';
    const begin=year==='rolling'?now-364*DAY:stamp(year+'-01-01');
    const end=year==='rolling'?now:Math.min(now,stamp((Number(year)+1)+'-01-01')-DAY);
    const days=[];
    for(let t=begin;t<=end;t+=DAY){const day=fromStamp(t);days.push({day,count:counts.get(day)||0,weekday:new Date(t).getUTCDay()});}
    const selected=dated.filter(p=>stamp(p.day)>=begin&&stamp(p.day)<=end);
    const within=(n,offset=0)=>dated.filter(p=>{const age=(now-stamp(p.day))/DAY;return age>=offset&&age<n+offset;});
    const tagCounts=new Map();
    for(const p of selected)for(const tag of new Set(p.tags||[]))tagCounts.set(tag,(tagCounts.get(tag)||0)+1);
    const tags=[...tagCounts].map(([label,count])=>({label,count})).sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));
    const difficulty=new Map();
    for(const p of selected){
      let label;
      if(p.rating!=null && Number.isFinite(Number(p.rating)) && ['codeforces','atcoder'].includes(p.platform)) {
        const start=Math.floor(Number(p.rating)/400)*400;
        label=`${p.platform==='codeforces'?'CF':'AT'} ${start}–${start+399}`;
      } else label=p.level?`${p.platform} ${p.level}`:`${p.platform} 未标定`;
      difficulty.set(label,(difficulty.get(label)||0)+1);
    }
    const monthly=new Map();
    for(const p of selected){const month=p.day.slice(0,7);if(!monthly.has(month))monthly.set(month,{});const m=monthly.get(month);m[p.platform]=(m[p.platform]||0)+1;}
    let currentStreak=0,probe=now;
    if(!counts.has(today))probe-=DAY;
    while(counts.has(fromStamp(probe))){currentStreak++;probe-=DAY;}
    return {today,year,years,solved,dated,selected,days,unknown,total:solved.length,
      periodTotal:selected.length,last30:within(30).length,previous30:within(30,30).length,last365:within(365).length,
      longest:streak(dated.map(p=>p.day)),periodLongest:streak(selected.map(p=>p.day)),monthLongest:streak(within(30).map(p=>p.day)),
      currentStreak,activeDays:new Set(selected.map(p=>p.day)).size,tags,
      tagged:selected.filter(p=>(p.tags||[]).length).length,
      difficulty:[...difficulty].map(([label,count])=>({label,count})).sort((a,b)=>b.count-a.count),
      monthly:[...monthly].sort(([a],[b])=>a.localeCompare(b)).map(([month,platforms])=>({month,platforms}))};
  }
  return {analyze,dayKey,streak};
});
