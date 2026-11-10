
import test from 'node:test';
import assert from 'node:assert/strict';
import {circledCount,reportMarkers} from '../src/coverage-report-markers.js';
test('报告按同轮计数，两张曲线按真实轮次终点关联，不补造位置',()=>{
 const point={run_id:'r1',tokens:1000,seconds:30,lines:100,weighted_lines:150};
 const series={runs:[point],token_points:[point],time_points:[point]};
 const reports=[{key:'a',project:'demo',runId:'r1'},{key:'b',project:'demo',runId:'r1'},
 {key:'b',project:'demo',runId:'r1'},{key:'c',project:'demo',runId:'missing'},
 {key:'d',project:'other',runId:'r1'}];
 for(const axis of ['tokens','seconds']){
  const result=reportMarkers(series,reports,'demo',axis);
  assert.equal(result.markers.length,1);assert.equal(result.markers[0].count,2);
  assert.equal(result.markers[0][axis],point[axis]);assert.equal(result.unplaced,1);
 }
 assert.equal(circledCount(1),'①');assert.equal(circledCount(2),'②');
 assert.equal(circledCount(21),'㉑');
});
test('没有可定位Token时只显示时间标记',()=>{
 const point={run_id:'r1',tokens:0,run_tokens:null,seconds:30,lines:100};
 const series={points:[point],time_points:[point]};
 const reports=[{key:'a',project:'demo',runId:'r1'}];
 assert.equal(reportMarkers(series,reports,'demo','tokens').markers.length,0);
 assert.equal(reportMarkers(series,reports,'demo','seconds').markers.length,1);
});
