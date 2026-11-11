import http from "node:http";
import https from "node:https";
import net from "node:net";
import tls from "node:tls";
import dns from "node:dns";
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";

const deny = () => { throw new Error("Offline count reproduction forbids network and subprocess access"); };
globalThis.fetch = deny;
for (const [module, names] of [
  [http, ["request", "get"]], [https, ["request", "get"]],
  [net, ["connect", "createConnection"]], [tls, ["connect"]],
  [dns, ["lookup", "resolve", "resolve4", "resolve6"]],
  [childProcess, ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync", "fork"]],
]) for (const name of names) module[name] = deny;
net.Socket.prototype.connect = deny;
syncBuiltinESMExports();
