import {useEffect,useState} from 'react';
import {createPortal} from 'react-dom';
import {X,Save,Loader2} from 'lucide-react';
import {api} from '../api.js';

const ROLES=[['audit','安全审计','负责代码分析与候选问题发现'],['verify','蓝队验证','负责候选问题验证'],['redteam','红队验证','负责隔离环境中的验证执行'],['environment','环境构建','负责依赖检查与环境准备'],['visual','攻击场景设计','负责场景分析与图文报告'],['judge','独立审核','负责审核红队验证证据']];
export default function ModelSettings({onClose}) {
  const [models,setModels]=useState(null);
  const [choices,setChoices]=useState([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [saved,setSaved]=useState(false);
  const load=async()=>{
    setError('');
    try {const data=await api.modelSettings();setModels(data.models);setChoices(data.choices);}
    catch(err){setError(err.message);}
  };
  useEffect(()=>{load();},[]);
  const save=async(event)=>{
    event.preventDefault();setBusy(true);setError('');setSaved(false);
    try {const data=await api.saveModelSettings(models);setModels(data.models);setSaved(true);}
    catch(err){setError(err.message);}
    finally {setBusy(false);}
  };
  return createPortal(<>
    <button className="project-import-backdrop" aria-label="关闭模型设置" disabled={busy} onClick={onClose}/>
    <form className="project-import-dialog model-settings-dialog" role="dialog" aria-modal="true" aria-labelledby="model-settings-title" onSubmit={save}>
      <header className="project-import-head"><div><h2 id="model-settings-title">阶段模型</h2><p>分别选择各阶段使用的模型</p></div><button type="button" className="icon-button" aria-label="关闭模型设置" disabled={busy} onClick={onClose}><X size={18}/></button></header>
      <div className="project-import-body">
        <p className="model-settings-note">保存后用于新导入和重新审计的任务，当前任务不受影响。</p>
        {!models && !error ? <p>正在读取模型配置…</p> : null}
        {models ? <div className="model-settings-grid">{ROLES.map(([role,label,hint])=><label className="model-settings-field" key={role}><strong>{label}</strong><input aria-label={`${label}模型`} list="stage-model-choices" value={models[role]} required={role==='audit'} maxLength={200} disabled={busy} placeholder="跟随安全审计模型" onChange={event=>{setModels({...models,[role]:event.target.value});setSaved(false);}}/><span>{hint}</span></label>)}</div> : null}
        <datalist id="stage-model-choices">{choices.map(model=><option key={model} value={model}/>)}</datalist>
        <p className="model-settings-help">可选择已有模型或输入名称；留空的阶段跟随安全审计模型。模型需在对应服务中可用。</p>
        {error ? <p className="project-import-error" role="alert">{error}{!models ? <button type="button" className="button" onClick={load}>重试</button>:null}</p>:null}
        {saved ? <p className="model-settings-saved" role="status">已保存，下次启动审计时生效。</p>:null}
      </div>
      <footer className="project-import-actions"><button type="button" className="button" onClick={onClose} disabled={busy}>关闭</button><button type="submit" className="button is-primary" disabled={!models||busy}>{busy?<Loader2 size={15} className="is-spinning"/>:<Save size={15}/>} {busy?'正在保存…':'保存设置'}</button></footer>
    </form>
  </>,document.body);
}
