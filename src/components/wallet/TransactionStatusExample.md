# Transaction Status Indicator - Visual Examples

## Example 1: High Confidence Transaction

**Scenario:** User withdrawing 0.64 MAVC with sufficient balance

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAVC Balance                                           │
│  1.29 MAVC                                              │
│  ≈ $25.43 USDC                                          │
│                                                         │
│  Amount (MAVC to withdraw)                              │
│  ┌─────────────────────────────────────┐               │
│  │ 0.64                                │               │
│  └─────────────────────────────────────┘               │
│                                                         │
│  You will receive approximately:                        │
│  $12.64 USDC                                            │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=====>                              ] 10%        │ │
│  │                                                   │ │
│  │ Validating transaction parameters...             │ │
│  │                                                   │ │
│  │ 🟢 Very likely to succeed (95%)                  │ │
│  │                                                   │ │
│  │ ▼ View risk factors                              │ │
│  │   Balance Margin      Network Congestion         │ │
│  │   50.4%               Low                        │ │
│  │   Gas Available       Contract Status            │ │
│  │   Yes                 Reachable                  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Withdraw MAVC    │  │ Cancel           │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Example 2: Low Balance Warning

**Scenario:** User trying to withdraw more than available

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAVC Balance                                           │
│  0.50 MAVC                                              │
│  ≈ $9.85 USDC                                           │
│                                                         │
│  Amount (MAVC to withdraw)                              │
│  ┌─────────────────────────────────────┐               │
│  │ 1.00                                │               │
│  └─────────────────────────────────────┘               │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=====>                              ] 10%        │ │
│  │                                                   │ │
│  │ Validating transaction parameters...             │ │
│  │                                                   │ │
│  │ 🔴 Very unlikely to succeed (5%)                 │ │
│  │                                                   │ │
│  │ ⚠ Insufficient balance for transaction           │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Withdraw MAVC    │  │ Cancel           │            │
│  │  (Disabled)      │  │                  │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Example 3: Processing Transaction

**Scenario:** Transaction submitted and broadcasting

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=============>                      ] 50%        │ │
│  │                                                   │ │
│  │ ⟳ Broadcasting to network...                     │ │
│  │                                                   │ │
│  │ 🟢 Very likely to succeed (90%)                  │ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Processing...    │  │ Cancel           │            │
│  │  (Disabled)      │  │  (Disabled)      │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Example 4: Confirming on Blockchain

**Scenario:** Transaction sent, waiting for blockchain confirmation

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=====================>              ] 75%        │ │
│  │                                                   │ │
│  │ ⟳ Waiting for blockchain confirmation...         │ │
│  │                                                   │ │
│  │ 🟢 Likely to succeed (85%)                       │ │
│  │                                                   │ │
│  │ Transaction: 0x1234abcd...5678ef90               │ │
│  │              View on Etherscan ↗                  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Processing...    │  │ Cancel           │            │
│  │  (Disabled)      │  │  (Disabled)      │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Example 5: Success!

**Scenario:** Transaction confirmed successfully

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│              ✓                                          │
│         Transaction Successful!                         │
│                                                         │
│    Your withdrawal has been processed                   │
│    successfully. Balance updated.                       │
│                                                         │
│                  ┌──────────┐                           │
│                  │   Done   │                           │
│                  └──────────┘                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Example 6: Multiple Warnings (Medium Risk)

**Scenario:** Close to balance limit with moderate network congestion

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAVC Balance                                           │
│  1.05 MAVC                                              │
│  ≈ $20.68 USDC                                          │
│                                                         │
│  Amount (MAVC to withdraw)                              │
│  ┌─────────────────────────────────────┐               │
│  │ 1.00                                │               │
│  └─────────────────────────────────────┘               │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=====>                              ] 10%        │ │
│  │                                                   │ │
│  │ Validating transaction parameters...             │ │
│  │                                                   │ │
│  │ 🟡 Uncertain (65%)                               │ │
│  │                                                   │ │
│  │ ⚠ Balance is very close to required amount       │ │
│  │ ⚠ Moderate network congestion                    │ │
│  │                                                   │ │
│  │ ▼ View risk factors                              │ │
│  │   Balance Margin      Network Congestion         │ │
│  │   4.8%                Medium                     │ │
│  │   Gas Available       Contract Status            │ │
│  │   Yes                 Reachable                  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Withdraw MAVC    │  │ Cancel           │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Example 7: Network Issues

**Scenario:** Unable to connect to blockchain

```
┌─────────────────────────────────────────────────────────┐
│  ← Withdraw MAVC                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  MAVC Balance                                           │
│  1.29 MAVC                                              │
│  ≈ $25.43 USDC                                          │
│                                                         │
│  Amount (MAVC to withdraw)                              │
│  ┌─────────────────────────────────────┐               │
│  │ 0.50                                │               │
│  └─────────────────────────────────────┘               │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ [=====>                              ] 10%        │ │
│  │                                                   │ │
│  │ Validating transaction parameters...             │ │
│  │                                                   │ │
│  │ 🟠 Unlikely (35%)                                │ │
│  │                                                   │ │
│  │ ⚠ Unable to reach blockchain network             │ │
│  │ ⚠ Cannot verify contract address                 │ │
│  │                                                   │ │
│  │ ▼ View risk factors                              │ │
│  │   Balance Margin      Network Congestion         │ │
│  │   61.2%               Unknown                    │ │
│  │   Gas Available       Contract Status            │ │
│  │   Unknown             Unreachable                │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Withdraw MAVC    │  │ Cancel           │            │
│  └──────────────────┘  └──────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## Color Coding Reference

| Color | Likelihood Level | Success Rate | Emoji |
|-------|-----------------|--------------|-------|
| 🟢 Green | Very Likely | 90-100% | 🟢 |
| 🟢 Light Green | Likely | 70-90% | 🟢 |
| 🟡 Yellow/Amber | Uncertain | 40-70% | 🟡 |
| 🟠 Orange | Unlikely | 10-40% | 🟠 |
| 🔴 Red | Very Unlikely | 0-10% | 🔴 |

---

## Risk Factor Color Coding

| Factor Status | Color | Example |
|--------------|-------|---------|
| Good | Green | Balance Margin: 45.2% |
| Warning | Yellow/Amber | Balance Margin: 3.1% |
| Error | Red | Balance Margin: -5.0% |

---

## Animation States

### Spinning Icon (Processing)
```
⟳  (rotating continuously)
```

### Success Checkmark
```
✓  (scales up with bounce effect)
```

### Error Cross
```
✗  (scales up with shake effect)
```

### Progress Bar Animations
- Smooth width transition (0.5s ease-out)
- Color changes based on stage
- Pulsing dot in likelihood badge

---

## Browser Compatibility

Tested and working in:
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

Animations use `framer-motion` which provides excellent cross-browser support.

---

## Accessibility Features

- Color is NOT the only indicator (text labels present)
- ARIA labels for screen readers
- Keyboard navigation support
- High contrast mode compatible
- Focus indicators on interactive elements

---

## Mobile Responsiveness

The component is fully responsive:
- Adapts to small screens
- Touch-friendly tap targets
- Readable font sizes
- Collapsible details for space savings

---

## Performance Notes

- Likelihood estimation runs async (non-blocking)
- Debounced on amount input (500ms)
- Minimal re-renders with React.memo
- Lightweight animations (GPU-accelerated)
- API calls cached for 15 minutes

---

These visual examples demonstrate the comprehensive feedback system that keeps users informed at every stage of their transaction!
