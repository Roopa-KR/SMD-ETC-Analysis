// Dashboard-only visualization and interaction. Every displayed value comes
// from server-calculated replay/scenario data, never from demo chart constants.
(() => {
  'use strict';
  const json = id => {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };
  const overview = json('analytics-data');
  const reference = json('chart-data');
  const chartTheme = {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family:'Inter, system-ui, sans-serif',size:10,color:'#98a5b7'},
    showlegend:false,
    margin:{t:10,b:36,l:40,r:16},
    hoverlabel:{bgcolor:'#1e2c45',font:{color:'#ffffff',size:11}}
  };
  const config = {displayModeBar:false,responsive:true,scrollZoom:false};
  const safePlot = (id, traces, layout) => {
    const el=document.getElementById(id);
    if (!el) return;
    if (!window.Plotly) { el.textContent='Chart unavailable; status values remain in the table below.'; return; }
    window.Plotly.newPlot(el,traces,layout,config).catch(() => {
      el.textContent='Unable to display chart. Use the accessible snapshot table below.';
    });
  };
  if (overview) {
    const rows=overview.trend;
    safePlot('risk-trend-chart', [
      {type:'scatter',mode:'lines+markers',x:rows.map(x=>x.time),y:rows.map(x=>x.on_time),
       name:'On-time share',line:{color:'#2563eb',width:3,shape:'spline',smoothing:.85},
       marker:{size:5,color:'#fff',line:{color:'#2563eb',width:2}},
       fill:'tozeroy',fillcolor:'rgba(37,99,235,.09)',
       hovertemplate:'%{x}<br><b>%{y:.1f}%</b> on time / fully picked<extra></extra>'}
    ],{...chartTheme,margin:{t:12,r:20,b:35,l:44},
       xaxis:{type:'category',tickfont:{size:9,color:'#a7b1c1'},showgrid:false,showline:false,ticks:'',
              nticks:7,automargin:true},
       yaxis:{range:[0,100],ticksuffix:'%',dtick:25,zeroline:false,gridcolor:'#f0f3f8',tickfont:{size:9},fixedrange:true},
       hovermode:'x unified'});
    const intervals=rows.filter(x=>x.completed!==null);
    const max=Math.max(1,...intervals.map(x=>x.completed));
    safePlot('activity-chart', [
      {type:'bar',x:intervals.map(x=>x.time),y:intervals.map(x=>x.completed),
       marker:{color:intervals.map((x,i)=>i===intervals.length-1?'#2563eb':
                           x.completed===max?'#5287f5':'#e5eaf2'),line:{width:0}},
       hovertemplate:'%{x}<br><b>%{y} lines</b> completed in 15 min<extra></extra>'}
    ],{...chartTheme,margin:{t:10,r:10,b:32,l:32},bargap:.45,barcornerradius:5,
       xaxis:{type:'category',showgrid:false,tickfont:{size:9,color:'#9ca9bd'},nticks:5},
       yaxis:{showgrid:true,gridcolor:'#f0f3f8',zeroline:false,nticks:4,tickfont:{size:9},rangemode:'tozero'}});
    if (!intervals.length) {
      const chart=document.getElementById('activity-chart');
      if (chart) chart.innerHTML='<p class="text-muted text-center small pt-5">No completed 15-minute interval is available yet.</p>';
    }
    // Gauge segments encode observed status shares, NOT invented risk thresholds.
    const m=overview.metrics, gauge=document.getElementById('gauge-segments');
    if(gauge && m.total>0) {
      const ns='http://www.w3.org/2000/svg', length=Math.PI*98;
      let offset=0;
      for (const [key,color] of [['healthy','#34c985'],['risk','#f0b74b'],
                                ['critical','#ef6873'],['unknown','#c8d0dc']]) {
        const amount=m[key] / m.total * length;
        if (amount<=0) continue;
        const p=document.createElementNS(ns,'path');
        p.setAttribute('d','M 22 121 A 98 98 0 0 1 218 121');
        p.setAttribute('fill','none');p.setAttribute('stroke',color);
        p.setAttribute('stroke-width','17');p.setAttribute('stroke-linecap','butt');
        p.setAttribute('stroke-dasharray',`${amount} ${length}`);
        p.setAttribute('stroke-dashoffset',String(-offset));
        gauge.appendChild(p);offset+=amount;
      }
    }
  }
  const table=document.getElementById('truck-table');
  if (table) {
    table.querySelectorAll('tbody tr[data-href]').forEach(row => {
      row.addEventListener('click', event => {
        if(event.target.closest('a,button')) return;
        window.location.assign(row.dataset.href);
      });
      row.addEventListener('keydown', event => {
        if(event.key==='Enter' && !event.target.closest('a,button')) window.location.assign(row.dataset.href);
      });
    });
    const body=table.querySelector('tbody');
    table.querySelectorAll('[data-sort]').forEach(button=>button.addEventListener('click',()=>{
      const header=button.closest('th'), index=[...header.parentElement.children].indexOf(header);
      const ascending=button.dataset.direction!=='asc';
      table.querySelectorAll('[data-sort]').forEach(b=>{if(b!==button)b.dataset.direction='';});
      button.dataset.direction=ascending?'asc':'desc';
      const rows=[...body.querySelectorAll('tr[data-href]')];
      const value=row=>row.cells[index]?.dataset.value || row.cells[index]?.textContent.trim() || '';
      rows.sort((a,b)=>{
        const left=value(a),right=value(b);
        const comparison=button.dataset.sort==='number'?Number(left)-Number(right):
          left.localeCompare(right,undefined,{numeric:true,sensitivity:'base'});
        return ascending?comparison:-comparison;
      });
      rows.forEach(row=>body.appendChild(row));
    }));
  }
  // Preserve the original ETC versus time-to-cutoff chart, on demand.
  const expanded=document.querySelector('.reference-chart details');
  if(expanded && reference) {
    let rendered=false;
    expanded.addEventListener('toggle',()=>{
      if (!expanded.open || rendered) return;
      rendered=true;
      const valid=reference.trucks.map((name,i)=>({name, etc:reference.etc[i], high:reference.etc_high[i],
                                                   cutoff:reference.cutoff[i],status:reference.status[i]}));
      if(!valid.length) {document.getElementById('etc-chart').textContent='No open truck work in this snapshot.';return;}
      safePlot('etc-chart',[
        {type:'bar',name:'Point ETC (h)',x:valid.map(x=>x.name),y:valid.map(x=>x.etc),
         marker:{color:valid.map(x=>x.status==='ON TIME'?'#34c985':'#ef6873')}},
        {type:'bar',name:'Hours to buffered cutoff',x:valid.map(x=>x.name),y:valid.map(x=>x.cutoff),
         marker:{color:'#cad5e7'}},
        {type:'scatter',mode:'markers',name:'Conservative ETC (h)',x:valid.map(x=>x.name),y:valid.map(x=>x.high),
         marker:{size:10,color:'#f0b74b',symbol:'line-ew-open'}},
        {type:'scatter',mode:'markers',name:'No observed rate',x:valid.filter(x=>x.etc===null).map(x=>x.name),
         y:valid.filter(x=>x.etc===null).map(()=>0),marker:{size:10,color:'#ad9dba',symbol:'x'}}
      ],{...chartTheme,barmode:'group',showlegend:true,
         legend:{orientation:'h',y:1.2,font:{size:10}},margin:{t:50,r:15,b:105,l:45},
         xaxis:{tickangle:-40,tickfont:{size:9}},yaxis:{title:'Hours',gridcolor:'#eff2f6'}});
    });
  }
})();
