"""NOTE (v11): after this script, run scripts/rescale_demo_labor.py. v11 replaced the WT1 x0.65 labor
calibration below with per-work-type scaling to the share of picked lines kept.

Build the 10-truck ACTIVE synthetic scenario workbook from archived reference facts.

Development-only build dependency: artifact_tool. The Flask app does not require it.
All retained operational events are explicitly labelled replay-derived synthetic demo data.
The unmodified 33-truck source remains in INFO/historical for audit only.
"""
from __future__ import annotations
from pathlib import Path
import math
import pandas as pd
from artifact_tool import Workbook, SpreadsheetFile
from calculations.excel_io import load_inputs

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'INFO/historical/historical_33_trucks_reference.xlsx'
DEST = ROOT / 'data/workbook.xlsx'
SHIPMENTS = ('SH0908-1034','SH0908-1069','SH0908-1035','SH0908-1020','SH0908-1003',
             'SH0908-1011','SH0908-1012','SH0908-1018','SH0908-1028','SH0908-1057')
MARK = 'SYNTHETIC 10-TRUCK PLANNING REPLAY (reference-derived, NOT live actual)'


def cells(frame):
    output = []
    for row in frame.itertuples(index=False, name=None):
        values=[]
        for v in row:
            if v is None or v is pd.NA or (isinstance(v,float) and (math.isnan(v) or math.isinf(v))):
                values.append(None)
            elif isinstance(v,pd.Timestamp):
                values.append(v.to_pydatetime())
            elif hasattr(v,'item') and callable(v.item):
                values.append(v.item())
            else: values.append(v)
        output.append(values)
    return output


def write_table(book,name,frame,header_row=2):
    ws=book.worksheets.add(name)
    if header_row>1:
        ws.get_range('A1').values=[[f'{name} — {MARK}']]
    if header_row>2:
        ws.get_range('A2').values=[['Active scenario source; 10 trucks. Historical reference archived separately.']]
    start=header_row-1
    data=[list(frame.columns)]+cells(frame)
    if data:
        ws.get_range_by_indexes(start,0,len(data),len(frame.columns)).values=data
    ws.get_range_by_indexes(start,0,1,len(frame.columns)).format.fill='#E8F0FF'
    return ws


def main():
    src=load_inputs(str(SOURCE))
    ships=src.shipments[src.shipments.SHIPMENTID.isin(SHIPMENTS)].copy()
    assert len(ships)==10
    # The synthetic appointment moves this truck's departure from 20:45 to 20:55;
    # risk is still derived from the conservative ETC engine (never a forced label).
    sh=ships.SHIPMENTID=='SH0908-1034'
    ships.loc[sh,'DEPARTURE_TIME'] += 10/1440
    ships.loc[sh,'ORIGINAL_DEPARTURE'] += 10/1440
    ships.loc[sh,'DOCK_DOOR']='D07'
    ships.loc[sh,'NOTE']='SYNTHETIC appointment: departure extended by 10 min from reference; buffer remains 10 min.'
    orders=src.orders[src.orders.ORIGINAL_SHIPMENTID.isin(SHIPMENTS)].copy()
    ids=src.line_map[src.line_map.WHORDERID.isin(orders.WHORDERID)].TI102ID
    line_map=src.line_map[src.line_map.TI102ID.isin(ids)].copy()
    ti=src.ti[src.ti.TI102ID.isin(ids)].copy()
    tc=src.tc[src.tc.TI102ID.isin(ids)].copy()
    assert set(orders.SHIPMENTID).issubset(SHIPMENTS)
    assert set(line_map.SHIPMENTID).issubset(SHIPMENTS)
    for frame in (ships,orders,line_map,ti,tc):
        if 'DATA_TYPE' in frame: frame['DATA_TYPE']=MARK
    lm=src.lm.copy()
    # Labor observations are historical warehouse-wide pace evidence used to support
    # a synthetic 10-truck queue; do not claim 30 days of individual performance.
    # Modelled WT1 labor effort = 65% of reference segment time, representing a
    # controlled, explicitly SYNTHETIC productivity uplift; no performance claim.
    # TOTALTIMEINMIN stays consistent with TOTALTIMEINSEC to avoid denominator drift.
    wt1 = lm.WORKTYPE.astype(int) == 1
    lm.loc[wt1, 'TOTALTIMEINSEC'] = (lm.loc[wt1, 'TOTALTIMEINSEC'] * 0.65).round().astype(int)
    lm.loc[wt1, 'TOTALTIMEINMIN'] = (lm.loc[wt1, 'TOTALTIMEINSEC'] / 60).round().astype(int)
    lm['DATA_TYPE']='SYNTHETIC LABOR REPLAY; WT1 time calibrated to 65% of historical segment'
    exp=src.operator_experience.copy()
    book=Workbook.create()
    conf=book.worksheets.add('CONFIG')
    conf.get_range('A1').values=[['SYNTHETIC 10-TRUCK DEMO; all status calculations are dynamic, no forced risk labels']]
    entries=[['SELECTED_SNAPSHOT_NO',10],['FOCUS_WORKTYPE',2],['ANALYSIS_DATE',src.config['ANALYSIS_DATE']],
             ['CLIENTID_FILTER','SMD'],['WHID_FILTER',100],['WIPIND_WORKING','Y'],['STATUS_COMPLETED',3]]
    conf.get_range('A4:B10').values=entries
    conf.get_range('A13:B13').values=[['SNAPSHOT_NO','T']]
    conf.get_range('A14:B31').values=cells(src.snapshots)
    tcg=book.worksheets.add('TRUCK_CONFIG')
    tcg.get_range('A1').values=[['SYNTHETIC TEN-TRUCK CONFIG; loading default 30 min; minimum buffer 10 min at runtime']]
    tcg.get_range('A6:B8').values=[['LOADING_MINUTES',30],['ORDER_LEAD_MINUTES',60],
                                ['REALLOCATION_EVIDENCE_RULE','OBSERVED_OR_LABELLED_SYNTHETIC_EXPERIENCE']]
    write_table(book,'LM005S1',lm,2)
    write_table(book,'TI102',ti,2)
    write_table(book,'TI102C',tc,2)
    write_table(book,'OB_SHIPMENT',ships,5)
    write_table(book,'OB_ORDER',orders,5)
    write_table(book,'OB_LINE_MAP',line_map,5)
    write_table(book,'OPERATOR_EXPERIENCE',exp,5)
    # Warehouse worktype lookup masters needed by the untouched Excel-reference calculation engine.
    m123=[];m123t=[]
    for wt,name in sorted(src.worktype_names.items()):
        m123.append([str(wt),None,None,None,None,int(wt)])
        m123t.append([None,str(wt),None,name])
    for name,arr,width in [('M123',m123,6),('M123T',m123t,4)]:
        ws=book.worksheets.add(name)
        ws.get_range('A1').values=[['SYNTHETIC REFERENCE WORKTYPE LOOKUP']]
        ws.get_range_by_indexes(2,0,len(arr),width).values=arr
    readme=book.worksheets.add('SCENARIO_README')
    readme.get_range('A1:B9').values=[
        ['ACTIVE DATASET','SYNTHETIC, NOT ACTUAL WAREHOUSE PERFORMANCE'],
        ['Trucks','Exactly 10; sources are filtered historical events and modeled departures'],
        ['Initial snapshot','10, 18:30 on 2026-09-08'],
        ['Risk status','Never hardcoded; evaluated by conservative ETC at departure-loading-10 min'],
        ['SH0908-1034','Departure extended 10 minutes as a documented synthetic appointment'],
        ['SH0908-1069','Original modeled departure used in synthetic scenario'],
        ['Operator pace','ONE recorded day; synthetic ten-truck subset; WT1 labor segments ×0.65; NOT actual monthly rate'],
        ['Experience','Synthetic cross-training entries explicitly labeled'],
        ['Archive','INFO/historical/historical_33_trucks_reference.xlsx excluded from active queries'],
    ]
    DEST.parent.mkdir(parents=True,exist_ok=True)
    SpreadsheetFile.export_xlsx(book).save(str(DEST))
    print('Generated',DEST,'10 trucks',len(orders),'orders',len(line_map),'lines',len(tc),'completed')

if __name__=='__main__':main()
