export interface WebhookEvent {
  readonly delivery_id: string;
  readonly event_type: string;
  readonly repository: string;
  readonly sender: string;
  readonly created_at: string;
  readonly processing_time_ms: number;
  readonly status: "success" | "failed";
  readonly [key: string]: unknown;
}
