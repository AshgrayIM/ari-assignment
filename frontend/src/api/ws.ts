import type { WsTradeMessage } from "../types/market";

type Handler = (msg: WsTradeMessage) => void;

export class MarketSocket {
  private ws: WebSocket | null = null;
  private handler: Handler | null = null;
  private reconnectDelay = 1000;
  private closedByUser = false;

  connect(handler: Handler): void {
    this.handler = handler;
    this.closedByUser = false;
    this.open();
  }

  private open(): void {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/market`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsTradeMessage;
        if (msg.type === "trade" && this.handler) {
          this.handler(msg);
        }
      } catch {
        // ignore malformed frames
      }
    };

    this.ws.onclose = () => {
      if (this.closedByUser) return;
      window.setTimeout(() => this.open(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 15000);
    };
  }

  close(): void {
    this.closedByUser = true;
    this.ws?.close();
    this.ws = null;
  }
}
