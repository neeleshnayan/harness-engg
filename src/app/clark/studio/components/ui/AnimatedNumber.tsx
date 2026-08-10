"use client";

import React, { useEffect, useState } from "react";
import { animate, useMotionValue, useTransform, motion } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  className?: string;
}

export function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  className = "",
}: AnimatedNumberProps) {
  const [directionColor, setDirectionColor] = useState<string>("");
  const motionValue = useMotionValue(value);
  
  // Transform the raw number into a formatted string
  const displayValue = useTransform(motionValue, (latest) => {
    return `${prefix}${latest.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}${suffix}`;
  });

  useEffect(() => {
    // Flash color on change
    if (value > motionValue.get()) {
      setDirectionColor("text-emerald-400");
    } else if (value < motionValue.get()) {
      setDirectionColor("text-rose-400");
    }

    const animation = animate(motionValue, value, {
      duration: 0.8,
      ease: "easeOut",
      onComplete: () => {
        setDirectionColor("");
      },
    });

    return animation.stop;
  }, [value, motionValue]);

  return (
    <motion.span
      className={`tabular-nums transition-colors duration-300 ${directionColor} ${className}`}
    >
      {displayValue}
    </motion.span>
  );
}
