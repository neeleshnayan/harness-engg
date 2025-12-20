"use client";

import React from "react";
import WalletPageBase, { WalletPageConfig } from "@/components/wallet/WalletPageBase";
import MiniClarkChat from '@/components/MiniClarkChat';

export default function CustomerPage() {

  const config: WalletPageConfig = {
    pageType: 'customer',
    growRoute: '/customer/grow',
    showKycStatusBadge: true,
    welcomeMessageMargin: '-mt-4',
    useERC20Modal: true,
    showChatToggle: true,
    renderChatComponent: ({ userId, onBalanceRefresh, onBalanceFlicker, onTransactionRefresh }) => (
      <MiniClarkChat
        userId={userId}
        onBalanceRefresh={onBalanceRefresh}
        onBalanceFlicker={onBalanceFlicker}
        onTransactionRefresh={onTransactionRefresh}
        showInputOnly={true}
      />
    ),
  };

  return <WalletPageBase config={config} />;
}
