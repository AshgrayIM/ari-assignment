export interface Ticker {
  symbol: string;
  last: number;
  percentage: number;
  quote_volume: number;
  base_volume: number;
  high: number;
  low: number;
}

export interface Kline {
  symbol: string;
  open_time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quote_volume: number;
  trade_count: number;
}

export interface Trade {
  symbol: string;
  trade_id: number;
  price: number;
  quantity: number;
  quote_qty: number;
  trade_time: string;
  is_buyer_maker: number;
}

export interface WsTradeMessage {
  type: "trade";
  data: Trade;
}
