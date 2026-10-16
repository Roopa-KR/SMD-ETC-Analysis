// Presentation and browser interaction only: all projection values originate in Flask.
// Draws the source-area impact chart and handles planner interactions.
(() => {
  'use strict';
  // v10: the target-truck before/after chart is drawn by ready_chart.js (shared with truck detail).
  const source = document.getElementById('planner-data');
  // Source chart: sequential before/after from the same conservative simulation,
  // with each source area's OWN buffered deadline. Never display an unsafe move as green.
  const sourcePanel=document.getElementById('source-impact-chart');
  if(sourcePanel && source){
    const data=JSON.parse(source.textContent);
    const mins=value=>{
      if(!value||value==='—')return null;
      const [h,m]=String(value).split(':').map(Number);
      return Number.isFinite(h)&&Number.isFinite(m)?h*60+m:null;
    };
    const rows=data.sources||[];
    const points=rows.filter(r=>mins(r.deadline)!==null);
    if(!window.Plotly || !points.length){
      sourcePanel.textContent='Source area has no measurable pending deadline, or chart rendering is unavailable. See source impact in the allocation review.';
    } else {
      const labels=points.map((r,i)=>`${r.operator} · WT ${r.worktype} · step ${i+1}`);
      const toTime=v=>v===null?'No pending source work':`${String(Math.floor(v/60)).padStart(2,'0')}:${String(v%60).padStart(2,'0')}`;
      const before=points.map(r=>mins(r.before)),after=points.map(r=>mins(r.after)),limits=points.map(r=>mins(r.deadline));
      const traces=[
        {name:'Source before removal',x:before,y:labels,marker:{color:'#91A4C0',size:12},mode:'markers',type:'scatter',hovertemplate:'<b>%{y}</b><br>Source before: %{customdata}<extra></extra>',customdata:before.map(toTime)},
        {name:'Source after removal',x:after,y:labels,marker:{color:points.map(r=>r.status_after==='ON TIME'?'#1ca77a':'#e05266'),size:13,symbol:'diamond'},mode:'markers',type:'scatter',hovertemplate:'<b>%{y}</b><br>Source after: %{customdata}<extra></extra>',customdata:after.map(toTime)},
        {name:'Required source deadline',x:limits,y:labels,marker:{color:'#E05266',size:11,symbol:'line-ns-open'},mode:'markers',type:'scatter',hovertemplate:'Source deadline %{customdata}<extra></extra>',customdata:limits.map(toTime)}];
      const times=[...before,...after,...limits].filter(v=>v!==null);
      if(!times.length){sourcePanel.textContent='Source work already complete; no source cutoff to plot.';}
      else {
        let lo=Math.min(...times)-12,hi=Math.max(...times)+12;
        const ticks=[];for(let t=Math.ceil(lo/30)*30;t<=hi;t+=30)ticks.push(t);
        Plotly.newPlot(sourcePanel,traces,{
          paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',
          font:{family:'Inter,system-ui,sans-serif',size:11,color:'#8794aa'},
          height:Math.max(210,110+65*points.length),margin:{l:190,r:24,t:28,b:45},
          showlegend:true,legend:{orientation:'h',y:1.22},
          xaxis:{range:[lo,hi],tickvals:ticks,ticktext:ticks.map(toTime),gridcolor:'#eef2f7',title:'Conservative completion vs buffered source deadline'},
          yaxis:{automargin:true,categoryorder:'array',categoryarray:labels.slice().reverse(),showgrid:false}
        },{responsive:true,displayModeBar:false}).catch(()=>{
          sourcePanel.textContent='Source plot unavailable. Exact times appear in the review panel.';
        });
      }
    }
  }
  const picker=document.querySelector('[data-loading-picker]');
  picker?.addEventListener('change',()=>{
    const url=new URL(picker.dataset.targetBase,window.location.origin);
    url.searchParams.set('shipment',picker.value);
    window.location.assign(url.toString());
  });
  const find=document.querySelector('[data-candidate-search]');
  find?.addEventListener('input',()=>{
    let shown=0;
    document.querySelectorAll('[data-candidate-row]').forEach(row=>{
      const match=row.textContent.toLocaleLowerCase().includes(find.value.trim().toLocaleLowerCase());
      row.hidden=!match;
      if(match) shown++;
    });
    const empty=document.querySelector('[data-candidate-empty]');
    if(empty) empty.hidden=shown>0 || !find.value.trim();
  });
  document.querySelector('[data-confirm-temporary]')?.addEventListener('submit',event=>{
    if(!window.confirm('Allocate these temporary operators (and any selected reallocations) for this session only? Original assignments, the workbook and the WMS are not changed.')) event.preventDefault();
  });
  document.querySelector('[data-confirm-allocation]')?.addEventListener('submit',event=>{
    if(!window.confirm('Confirm this advisory allocation scenario? Historical facts and WMS assignments will not change.')) event.preventDefault();
  });
})();
