/**
 * MongoDB ulanishi.
 *
 * Ulanish DANGASA: birinchi murojaatda ochiladi va keyin qayta ishlatiladi.
 * Ishlab chiqish rejimida Next.js modullarni qayta yuklaydi, shuning uchun
 * mijoz `globalThis` da saqlanadi — aks holda har tahrirdan keyin yangi
 * ulanish hovuzi ochilib, Mongo ulanish limitiga urilib qolardi.
 *
 * MUHIM: Mongo ishlamayotgan bo'lsa sayt to'xtamaydi. Savol-javob, hujjat
 * tahlili va qonun bazasi Mongo ga bog'liq emas — faqat kabinet, tarix va
 * statistika o'chadi. Shuning uchun `tryGetDb()` xatolik o'rniga `null` beradi.
 */

import { MongoClient, type Db } from "mongodb";
import { config } from "../config";

interface MongoCache {
  client: MongoClient | null;
  promise: Promise<MongoClient> | null;
  /** Oxirgi ulanish xatosi — panelda ko'rsatish uchun. */
  lastError: string | null;
}

const globalForMongo = globalThis as unknown as { __aiLowyerMongo?: MongoCache };

const cache: MongoCache = (globalForMongo.__aiLowyerMongo ??= {
  client: null,
  promise: null,
  lastError: null,
});

export function isMongoConfigured(): boolean {
  return config.mongoEnabled;
}

/** Oxirgi ulanish xatosi (bo'lsa). */
export function mongoLastError(): string | null {
  return cache.lastError;
}

async function connect(): Promise<MongoClient> {
  const uri = config.mongoUri;
  if (!uri) throw new Error("MONGODB_URI sozlanmagan.");

  if (cache.client) return cache.client;
  if (cache.promise) return cache.promise;

  cache.promise = new MongoClient(uri, {
    // Mongo o'chiq bo'lsa so'rov 30 soniya osilib turmasligi kerak.
    serverSelectionTimeoutMS: 3000,
    connectTimeoutMS: 3000,
  })
    .connect()
    .then((client) => {
      cache.client = client;
      cache.lastError = null;
      return client;
    })
    .catch((err: unknown) => {
      cache.promise = null;
      cache.lastError = err instanceof Error ? err.message : String(err);
      throw err;
    });

  return cache.promise;
}

/** Bazani qaytaradi. Ulanmasa xato tashlaydi. */
export async function getDb(): Promise<Db> {
  if (!config.mongoUri) {
    throw new Error(
      "Maʼlumotlar bazasi sozlanmagan. `.env.local` ga MONGODB_URI qoʻshing.",
    );
  }
  const client = await connect();
  return client.db(config.mongoDbName);
}

/** Bazani qaytaradi, ulanmasa `null`. Yozib qo'yish yo'llari uchun. */
export async function tryGetDb(): Promise<Db | null> {
  try {
    return await getDb();
  } catch {
    return null;
  }
}

/** Ulanishni yopadi (CLI va testlar uchun). */
export async function closeMongo(): Promise<void> {
  await cache.client?.close().catch(() => {});
  cache.client = null;
  cache.promise = null;
}

/** Baza tirikmi — panel «tizim holati» uchun. */
export async function pingMongo(): Promise<{ ok: boolean; error?: string }> {
  if (!config.mongoUri) return { ok: false, error: "MONGODB_URI sozlanmagan." };
  try {
    const db = await getDb();
    await db.command({ ping: 1 });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "ulanmadi" };
  }
}
