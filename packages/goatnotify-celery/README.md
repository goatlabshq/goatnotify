# goatnotify-celery

Celery queue for GoatNotify in Django projects. Delivery receipts make retries and redeliveries
idempotent: a message already sent is never sent again.

```bash
pip install goatnotify-celery
```

Documentation: <https://goatlabshq.github.io/goatnotify/queues/#celery>
