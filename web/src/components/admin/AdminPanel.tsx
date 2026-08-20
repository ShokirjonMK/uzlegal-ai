"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HolatBolimi } from "./HolatBolimi";
import { YadroBolimi } from "./YadroBolimi";
import { BazaBolimi } from "./BazaBolimi";
import { YozishmalarBolimi } from "./YozishmalarBolimi";
import { XabarBolimi } from "./XabarBolimi";

/**
 * Panel qobig'i.
 *
 * Bo'limlar orasida yurish sahifani qayta yuklamaydi — hammasi bitta mijoz
 * komponentida (SPA). Har bir bo'lim o'z ma'lumotini o'zi oladi va faqat
 * ochilganda oladi: panel ochilishi bilan to'rtta so'rov ketmaydi.
 */
export function AdminPanel() {
  const router = useRouter();
  const [chiqmoqda, setChiqmoqda] = useState(false);

  async function chiqish() {
    setChiqmoqda(true);
    try {
      await fetch("/api/admin/kirish", { method: "DELETE" });
    } finally {
      router.refresh();
    }
  }

  return (
    <>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1>Admin panel</h1>
          <p className="lede mb-4">
            Qonun bazasi, statistika, tizim holati va ommaviy xabar.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void chiqish()} disabled={chiqmoqda}>
          <LogOut />
          Chiqish
        </Button>
      </div>

      <Tabs defaultValue="yadro">
        <TabsList>
          <TabsTrigger value="yadro">Yadro</TabsTrigger>
          <TabsTrigger value="holat">Umumiy holat</TabsTrigger>
          <TabsTrigger value="baza">Qonun bazasi</TabsTrigger>
          <TabsTrigger value="yozishmalar">Yozishmalar</TabsTrigger>
          <TabsTrigger value="xabar">Ommaviy xabar</TabsTrigger>
        </TabsList>

        <TabsContent value="yadro">
          <YadroBolimi />
        </TabsContent>

        <TabsContent value="holat">
          <HolatBolimi />
        </TabsContent>
        <TabsContent value="baza">
          <BazaBolimi />
        </TabsContent>
        <TabsContent value="yozishmalar">
          <YozishmalarBolimi />
        </TabsContent>
        <TabsContent value="xabar">
          <XabarBolimi />
        </TabsContent>
      </Tabs>
    </>
  );
}
