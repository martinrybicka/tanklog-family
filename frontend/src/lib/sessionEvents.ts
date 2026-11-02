// Pouze dočasný signál mezi okny téhož originu, bez údajů účtu nebo úložiště.
export function announceLogout() {
  if (!("BroadcastChannel" in window)) return;
  const channel = new BroadcastChannel("tanklog-session");
  channel.postMessage("logout");
  channel.close();
}
