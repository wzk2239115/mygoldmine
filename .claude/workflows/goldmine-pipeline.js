export const meta = {
  name: 'goldmine-pipeline',
  description: '按磁盘回执执行审计节点，保留已有产物检查与发布条件',
}

if (!args || !Array.isArray(args.steps) || !args.command) throw new Error('缺少已登记的执行计划')
const receipts = []
for (const step of args.steps) {
  phase(step.title)
  const receipt = await agent(
    `你只负责启动一个已登记的审计节点。使用 Bash 原样执行下列命令，该命令只登记或查询独立任务，很快返回 JSON；原样返回其 node 与 status。不要追加 echo 或其他命令，不要添加日志重定向。不要在这里等待实际构建，不要使用 Task 充当后台输出查询工具。status=running 表示任务已登记，由宿主机按磁盘状态继续等待；不能改写为 completed。不要修改文件，不要另行审计，不要改变候选范围，不要自行跳过或重试。\n${args.command} --node ${step.node}\n执行失败立即报告失败。磁盘回执才是完成依据。`,
    {label: step.title, schema: {type:'object',properties:{node:{type:'string',enum:[step.node]},status:{type:'string',enum:['completed','degraded','blocked','skipped','failed','running']}},required:['node','status'],additionalProperties:false}},
  )
  if(receipt?.status==='running')return {status:'waiting',node:step.node};
  if (!receipt || receipt.node !== step.node || !['completed','degraded','blocked','skipped'].includes(receipt.status)) {
    throw new Error(`节点未完成：${step.node}`)
  }
  receipts.push(receipt)
}
return receipts
