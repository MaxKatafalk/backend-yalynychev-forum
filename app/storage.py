from threading import RLock

from .schemas import Topic, TopicCreate, TopicListQuery, TopicPatch


class TopicStore:
    def __init__(self):
        self._topics: dict[int, Topic] = {}
        self._next_id = 1
        self._lock = RLock()

    def create(self, data: TopicCreate) -> Topic:
        with self._lock:
            topic = Topic(id=self._next_id, **data.model_dump())
            self._topics[topic.id] = topic
            self._next_id += 1
            return topic

    def get(self, topic_id: int) -> Topic | None:
        with self._lock:
            return self._topics.get(topic_id)

    def list(self, query: TopicListQuery) -> list[Topic]:
        with self._lock:
            topics = sorted(self._topics.values(), key=lambda topic: topic.id)
            if query.author is not None:
                topics = [topic for topic in topics if topic.author == query.author]
            if query.status is not None:
                topics = [topic for topic in topics if topic.status == query.status]
            return topics[query.offset:query.offset + query.limit]

    def update(self, topic_id: int, data: TopicPatch) -> Topic | None:
        with self._lock:
            current = self._topics.get(topic_id)
            if current is None:
                return None
            updated = Topic.model_validate({**current.model_dump(), **data.model_dump(exclude_unset=True)})
            self._topics[topic_id] = updated
            return updated

    def delete(self, topic_id: int) -> bool:
        with self._lock:
            return self._topics.pop(topic_id, None) is not None
