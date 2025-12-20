"use client";

import React from "react";
import { FaBuilding } from "react-icons/fa";
import WalletPageBase, { WalletPageConfig } from "@/components/wallet/WalletPageBase";
import MiniClarkChat from '@/components/MiniClarkChat';

export default function BusinessPage() {
  const config: WalletPageConfig = {
    pageType: 'business',
    growRoute: '/business/grow',
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
    renderAdditionalActionButtons: (push) => (
      <button
        type="button"
        onClick={() => push('/business/manage')}
        className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white py-5 px-10 rounded-full font-bold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-xl"
      >
        <FaBuilding className="mr-3 text-lg text-white" />
        Manage Business
      </button>
    ),
  };

  return <WalletPageBase config={config} />;
}
