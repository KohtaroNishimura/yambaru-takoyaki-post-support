"use client";

import { useMemo, useState } from "react";

type TodayInfo = {
  date: string;
  weekday: string;
  weather: string;
  temperature_c: number;
  sunrise: string;
  sunset: string;
  old_calendar: string;
  rokuyo: string;
  sekki24: string;
  okinawa_event: string;
  tide: string;
  local_tip: string;
  location: string;
  business_hours: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Page() {
  const [post, setPost] = useState("");
  const [info, setInfo] = useState<TodayInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const chars = useMemo(() => post.length, [post]);

  const generate = async () => {
    setLoading(true);
    setError("");
    setCopied(false);

    try {
      const res = await fetch(`${apiBase}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error("投稿生成に失敗しました");

      const data = await res.json();
      setPost(data.post ?? "");
      setInfo(data.info ?? null);
    } catch (e) {
      const message = e instanceof Error ? e.message : "不明なエラー";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!post) return;
    await navigator.clipboard.writeText(post);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <main>
      <section className="rounded-2xl border border-orange-200 bg-white/90 p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-ocean">やんばる あちこーこー たこ焼き 投稿サポート</h1>
        <p className="mt-2 text-sm text-zinc-700">営業前30秒で、今日の投稿を作成できます。</p>

        <div className="mt-5">
          <button
            onClick={generate}
            disabled={loading}
            className="h-11 rounded-xl bg-primary px-6 font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "生成中..." : "投稿を生成"}
          </button>
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-sky-200 bg-white/90 p-5 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ocean">生成された投稿</h2>
            <span className="text-xs text-zinc-500">{chars}文字</span>
          </div>
          <textarea
            value={post}
            onChange={(e) => setPost(e.target.value)}
            placeholder="投稿を生成するとここに表示されます"
            className="h-72 w-full rounded-xl border border-zinc-300 bg-white p-3 text-sm leading-6"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={copy}
              disabled={!post}
              className="rounded-xl bg-leaf px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              コピー
            </button>
            {copied && <span className="text-sm text-leaf">コピーしました</span>}
          </div>
        </article>

        <article className="rounded-2xl border border-orange-200 bg-white/90 p-5 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-ocean">今日の取得情報</h2>
          {!info ? (
            <p className="text-sm text-zinc-600">投稿生成後に表示されます。</p>
          ) : (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt>日付</dt><dd>{info.date}（{info.weekday}）</dd>
              <dt>天気</dt><dd>{info.weather}</dd>
              <dt>気温</dt><dd>{info.temperature_c.toFixed(1)}℃</dd>
              <dt>日の出 / 日の入</dt><dd>{info.sunrise} / {info.sunset}</dd>
              <dt>旧暦</dt><dd>{info.old_calendar}</dd>
              <dt>六曜</dt><dd>{info.rokuyo}</dd>
              <dt>二十四節気</dt><dd>{info.sekki24}</dd>
              <dt>沖縄行事</dt><dd>{info.okinawa_event}</dd>
              <dt>潮汐</dt><dd>{info.tide}</dd>
              <dt>沖縄小ネタ</dt><dd>{info.local_tip}</dd>
              <dt>出店場所</dt><dd>{info.location}</dd>
              <dt>営業時間</dt><dd>{info.business_hours}</dd>
            </dl>
          )}
        </article>
      </section>
    </main>
  );
}
