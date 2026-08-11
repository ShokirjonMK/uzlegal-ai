"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FolderSync, Trash2, Upload, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface Korpus {
  chunks: number;
  documents: Array<{ document: string; chunks: number }>;
  embedder?: string;
}

interface BazaJavobi {
  korpus: Korpus;
  papka?: string;
  xabar?: string;
}

export function BazaBolimi() {
  const [korpus, setKorpus] = useState<Korpus | null>(null);
  const [papka, setPapka] = useState("");
  const [xato, setXato] = useState("");
  const [xabar, setXabar] = useState("");
  const [amal, setAmal] = useState<"" | "yuklash" | "papka" | "ochirish">("");
  const [ochiriladigan, setOchiriladigan] = useState<string | null>(null);
  const [tasdiq, setTasdiq] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const yukla = useCallback(async () => {
    setXato("");
    try {
      const javob = await apiJson<BazaJavobi>("/api/admin/baza");
      setKorpus(javob.korpus);
      if (javob.papka) setPapka(javob.papka);
    } catch (err) {
      setXato(humanError(err));
    }
  }, []);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  async function faylYukla(file: File) {
    setAmal("yuklash");
    setXato("");
    setXabar("");
    try {
      const form = new FormData();
      form.append("file", file);
      const javob = await apiJson<BazaJavobi>("/api/admin/baza", {
        method: "POST",
        body: form,
      });
      setKorpus(javob.korpus);
      setXabar(javob.xabar ?? "Yuklandi.");
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setAmal("");
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function papkadanYukla() {
    setAmal("papka");
    setXato("");
    setXabar("");
    try {
      const javob = await apiJson<BazaJavobi>("/api/admin/baza", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ amal: "papka" }),
      });
      setKorpus(javob.korpus);
      setXabar(javob.xabar ?? "Yuklandi.");
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setAmal("");
    }
  }

  async function ochir() {
    if (!ochiriladigan) return;
    setAmal("ochirish");
    setXato("");
    setXabar("");
    try {
      const javob = await apiJson<BazaJavobi>(
        `/api/admin/baza?hujjat=${encodeURIComponent(ochiriladigan)}`,
        { method: "DELETE" },
      );
      setKorpus(javob.korpus);
      setXabar(javob.xabar ?? "Oʻchirildi.");
      setOchiriladigan(null);
      setTasdiq("");
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setAmal("");
    }
  }

  const band = amal !== "";

  return (
    <>
      <Card className="mb-3">
        <CardHeader>
          <CardTitle>Hujjat qoʻshish</CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="fayl">Fayl (PDF, DOCX, TXT, MD, HTML — 25 MB gacha)</Label>
          <Input
            id="fayl"
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md,.html,.htm"
            disabled={band}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void faylYukla(f);
            }}
          />
          <p className="text-[13px] text-faint mt-2">
            Fayl nomi hujjat nomi boʻlib qoladi. Shu nomdagi hujjat bazada boʻlsa —
            eski boʻlaklari almashtiriladi.
          </p>

          <div className="actions">
            <Button variant="ghost" disabled={band} onClick={() => void papkadanYukla()}>
              {amal === "papka" ? <Loader2 className="animate-spin" /> : <FolderSync />}
              {amal === "papka" ? "Yuklanmoqda…" : "Papkadagi hammasini yuklash"}
            </Button>
            <Button variant="plain" size="sm" disabled={band} onClick={() => void yukla()}>
              <RefreshCw />
              Yangilash
            </Button>
          </div>

          {papka && (
            <p className="text-[12.5px] text-faint mt-2 mb-0">
              Papka: <span className="mono">{papka}</span>
            </p>
          )}

          {amal === "yuklash" && (
            <p className="status mt-2" aria-live="polite">
              <Upload className="inline size-3.5 mr-1.5 align-[-2px]" />
              Fayl yuklanmoqda va vektorlashtirilmoqda… Bu bir necha daqiqa olishi mumkin.
            </p>
          )}
        </CardContent>
      </Card>

      {xato && (
        <div className="alert" role="alert">
          {xato}
        </div>
      )}
      {xabar && (
        <div className="notice" role="status">
          {xabar}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            Bazadagi hujjatlar{korpus ? ` (${korpus.documents.length})` : ""}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!korpus ? (
            <div aria-busy="true">
              {Array.from({ length: 3 }, (_, i) => (
                <div key={i} className="skeleton skeleton-line" style={{ height: 20 }} />
              ))}
            </div>
          ) : korpus.documents.length === 0 ? (
            <p className="dim m-0">
              Baza boʻsh. Yuqoridan fayl yuklang yoki qonun matnlarini{" "}
              <span className="mono">data/corpus/</span> papkasiga joylab, «Papkadagi
              hammasini yuklash» tugmasini bosing.
            </p>
          ) : (
            <>
              {korpus.documents.map((d) => (
                <div key={d.document} className="doc-row">
                  <div>
                    <div className="name">{d.document}</div>
                    <div className="text-[13px] text-faint">{d.chunks} boʻlak</div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={band}
                    onClick={() => {
                      setOchiriladigan(d.document);
                      setTasdiq("");
                    }}
                  >
                    <Trash2 />
                    Oʻchirish
                  </Button>
                </div>
              ))}
              <p className="text-[13px] text-faint mt-3 mb-0">
                Jami: {korpus.chunks} boʻlak · Embedder: {korpus.embedder ?? "—"}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* O'chirish qaytarib bo'lmaydi — hujjat nomini qo'lda yozish talab qilinadi. */}
      <Dialog
        open={ochiriladigan !== null}
        onOpenChange={(open) => {
          if (!open) {
            setOchiriladigan(null);
            setTasdiq("");
          }
        }}
      >
        <DialogContent title="Hujjatni oʻchirish">
          <DialogDescription>
            «{ochiriladigan}» bazadan butunlay oʻchiriladi. Buni qaytarib boʻlmaydi —
            hujjatni qaytadan yuklashingiz kerak boʻladi.
          </DialogDescription>
          <Label htmlFor="tasdiq">
            Tasdiqlash uchun hujjat nomini yozing
          </Label>
          <Input
            id="tasdiq"
            value={tasdiq}
            autoFocus
            disabled={band}
            onChange={(e) => setTasdiq(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="destructive"
              disabled={band || tasdiq !== ochiriladigan}
              onClick={() => void ochir()}
            >
              {amal === "ochirish" && <Loader2 className="animate-spin" />}
              Oʻchirish
            </Button>
            <DialogClose asChild>
              <Button variant="ghost" disabled={band}>
                Bekor qilish
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
