"use client";

import React, { useEffect, useRef } from "react";
import lottie from "lottie-web";

interface WalletProgressStateProps {
  heading: string;
  detail: string;
  animationPath: string;
  closeCountdown: number;
}

export default function WalletProgressState({
  heading,
  detail,
  animationPath,
  closeCountdown,
}: WalletProgressStateProps) {
  const animationContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!animationContainerRef.current) {
      return;
    }

    const animation = lottie.loadAnimation({
      container: animationContainerRef.current,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path: animationPath,
      rendererSettings: {
        preserveAspectRatio: "xMidYMid meet",
      },
    });

    return () => {
      animation.destroy();
    };
  }, [animationPath]);

  return (
    <div className="flex flex-col items-center justify-center py-6 cursor-pointer min-h-[420px]">
      <div ref={animationContainerRef} className="w-[190px] h-[190px] mb-3" aria-label={heading} />
      <div className="text-[#90E7EE] text-2xl font-medium leading-tight tracking-tight mb-3">{heading}</div>
      <div className="text-white text-xl font-normal leading-tight text-center px-2">{detail}</div>
      <div className="mt-auto pt-16 text-[#90E7EE]/70 text-[16px] font-medium">
        Tap anywhere to close{closeCountdown > 0 && ` (${closeCountdown}s)`}
      </div>
    </div>
  );
}
