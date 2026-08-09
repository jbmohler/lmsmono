import { Injectable, NgZone, inject } from '@angular/core';
import { Observable, Subject } from 'rxjs';
import { filter } from 'rxjs/operators';

/**
 * A committed change to a server-side resource, pushed from the backend.
 *
 * These are invalidation hints, not data - act on one by refetching through the
 * normal API.
 */
export interface ChangeEvent {
  /** Capability namespace of the resource, e.g. "transactions" */
  entity: string;
  action: 'created' | 'updated' | 'deleted';
  id: string | null;
  /** User id that made the change */
  actor: string | null;
}

const STREAM_URL = '/api/events';
const BROADCAST_CHANNEL = 'lms-changes';
const LEADER_LOCK = 'lms-change-stream';

/**
 * Delivers backend change notifications to every open tab over a single
 * server-sent event stream.
 *
 * One tab wins a Web Lock and holds the only EventSource; it rebroadcasts each
 * event to its siblings over a BroadcastChannel. Without that election, N tabs
 * open N streams, and HTTP/1.1's six-connection-per-origin cap would starve the
 * seventh tab of ordinary XHRs too.
 */
@Injectable({ providedIn: 'root' })
export class ChangeNotificationService {
  private zone = inject(NgZone);

  private events$ = new Subject<ChangeEvent>();
  private channel: BroadcastChannel | null = null;
  private source: EventSource | null = null;
  private releaseLeadership: (() => void) | null = null;
  private pendingLeadership: AbortController | null = null;

  /** Begin receiving notifications. Safe to call repeatedly. */
  start(): void {
    if (this.channel) {
      return;
    }
    this.channel = new BroadcastChannel(BROADCAST_CHANNEL);
    this.channel.onmessage = (message: MessageEvent<ChangeEvent>) => this.emit(message.data);
    this.acquireStream();
  }

  /** Drop the stream and stop listening. Safe to call when not started. */
  stop(): void {
    this.source?.close();
    this.source = null;
    this.pendingLeadership?.abort();
    this.pendingLeadership = null;
    this.releaseLeadership?.();
    this.releaseLeadership = null;
    this.channel?.close();
    this.channel = null;
  }

  /** Changes to one resource, e.g. `forEntity('transactions')`. */
  forEntity(entity: string): Observable<ChangeEvent> {
    return this.events$.pipe(filter((event) => event.entity === entity));
  }

  private acquireStream(): void {
    if (!('locks' in navigator)) {
      this.openStream();
      return;
    }

    const pending = new AbortController();
    this.pendingLeadership = pending;

    navigator.locks
      .request(
        LEADER_LOCK,
        { signal: pending.signal },
        () =>
          // Held until stop() resolves it or this tab goes away, at which point
          // the next queued tab takes over the stream on its own.
          new Promise<void>((resolve) => {
            this.pendingLeadership = null;
            this.releaseLeadership = resolve;
            this.openStream();
          })
      )
      .catch(() => undefined); // AbortError when stop() beats the grant
  }

  private openStream(): void {
    const source = new EventSource(STREAM_URL);
    this.source = source;

    source.onmessage = (message: MessageEvent<string>) => {
      let event: ChangeEvent;
      try {
        event = JSON.parse(message.data) as ChangeEvent;
      } catch {
        return;
      }
      this.emit(event);
      this.channel?.postMessage(event);
    };

    source.onerror = () => {
      // A dropped connection sets CONNECTING and EventSource retries itself. A
      // non-2xx response - an expired session, most often - sets CLOSED and it
      // never retries, so release the lock and wait for start() after re-login.
      if (source.readyState === EventSource.CLOSED) {
        this.stop();
      }
    };
  }

  private emit(event: ChangeEvent): void {
    // EventSource and BroadcastChannel callbacks can land outside Angular's
    // zone; without this the refetch they trigger renders nothing.
    this.zone.run(() => this.events$.next(event));
  }
}
