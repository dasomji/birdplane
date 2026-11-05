export function assertDisposable({ project, image, databaseUrl, redisUrl }) {
  const db = new URL(databaseUrl);
  const redis = new URL(redisUrl);
  if (
    !/^kitchen-verify-[a-f0-9]{12}-[a-f0-9]{12}$/.test(project) ||
    image !== `${project}:test` ||
    db.protocol !== "postgresql:" ||
    db.hostname !== "verify-db" ||
    db.port !== "5432" ||
    db.pathname !== "/verify" ||
    db.username !== "verify" ||
    db.search ||
    db.hash ||
    redis.href !== "redis://verify-redis:6379/0"
  )
    throw new Error("Refusing non-disposable destination");
}
