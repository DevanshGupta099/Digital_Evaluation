import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["events"])

class EventPublisher:
    def __init__(self):
        self.queues = []

    def subscribe(self):
        q = asyncio.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q):
        if q in self.queues:
            self.queues.remove(q)

    async def publish(self, event_type: str, data: dict):
        # Fire and forget publishing
        for q in self.queues:
            await q.put({"event": event_type, "data": data})
            
        # If it's a notification, persist it to the DB
        if event_type == "notification":
            from app.database.session import AsyncSessionLocal
            from app.database.models import Notification
            async with AsyncSessionLocal() as db:
                try:
                    notif = Notification(
                        class_offering_id=data.get("class_offering_id"),
                        type=data.get("type", "info"),
                        message=data.get("message", "")
                    )
                    db.add(notif)
                    await db.commit()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to save notification: {e}")

publisher = EventPublisher()

@router.get("/api/stream/events")
async def stream_events(offering_id: str = None):
    async def event_generator():
        q = publisher.subscribe()
        try:
            while True:
                msg = await q.get()
                # Check offering_id filter
                msg_offering_id = msg.get("data", {}).get("class_offering_id")
                if offering_id and msg_offering_id and msg_offering_id != offering_id:
                    continue
                    
                # Format as SSE
                event_type = msg.get("event", "message")
                data_str = json.dumps(msg.get("data", {}))
                yield f"event: {event_type}\ndata: {data_str}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            publisher.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.database.models import Notification

@router.get("/api/offerings/{offering_id}/notifications")
async def get_notifications(offering_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notification)
        .where(Notification.class_offering_id == offering_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = result.scalars().all()
    return [{
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "is_read": n.is_read,
        "created_at": n.created_at
    } for n in notifs]

@router.put("/api/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, db: AsyncSession = Depends(get_db)):
    notif = await db.get(Notification, notif_id)
    if notif:
        notif.is_read = True
        await db.commit()
    return {"status": "success"}
