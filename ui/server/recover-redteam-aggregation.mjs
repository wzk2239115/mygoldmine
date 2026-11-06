import {recoverExecutionAggregation} from './redteam-agent-retry.mjs';
try {if(!process.argv[2])throw Error('需要 attempt.json 路径');console.log(JSON.stringify(recoverExecutionAggregation(process.argv[2])));}catch(error){console.error(error.message);process.exitCode=1;}
