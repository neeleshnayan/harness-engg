"use client";

import React from "react";
import WalletPageBase, { WalletPageConfig } from "@/components/wallet/WalletPageBase";
import MiniHedgeFundChat from '@/components/MiniHedgeFundChat';

export default function CustomerPage() {
  const config: WalletPageConfig = {
    pageType: 'customer',
    growRoute: '/customer/grow',
    showKycStatusBadge: true,
    welcomeMessageMargin: '-mt-4',
    useERC20Modal: true,
    showChatToggle: true,
    renderChatComponent: ({ userId, onBalanceRefresh, onBalanceFlicker, onTransactionRefresh }) => (
      <MiniHedgeFundChat
        userId={userId}
        onBalanceRefresh={onBalanceRefresh}
        onBalanceFlicker={onBalanceFlicker}
        onTransactionRefresh={onTransactionRefresh}
      />
    ),
  };

  return <WalletPageBase config={config} />;
}
