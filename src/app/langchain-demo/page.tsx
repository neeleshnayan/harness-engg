import LangChainChat from '@/components/LangChainChat';

export default function LangChainDemoPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#001C1B] text-white">
      <div className="absolute inset-0">
        <div className="absolute -left-24 top-16 h-64 w-64 rounded-full bg-emerald-500/20 blur-[140px]" />
        <div className="absolute right-[-20%] top-40 h-96 w-96 rounded-full bg-indigo-500/10 blur-[160px]" />
        <div className="absolute bottom-0 left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-emerald-400/15 blur-[160px]" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center justify-center gap-16 px-6 py-16">
        <div className="max-w-2xl text-center">
          <p className="text-sm uppercase tracking-[0.3em] text-white/50">Clark</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            A sleek LangChain chat experience for lightning-fast crypto actions.
          </h1>
          <p className="mt-4 text-base text-white/60">
            Trigger transfers, check balances, and manage automated trading with plain language. Meet Clark—the
            always-on co-pilot for your digital assets.
          </p>
        </div>

        <LangChainChat />
      </div>
    </div>
  );
}
