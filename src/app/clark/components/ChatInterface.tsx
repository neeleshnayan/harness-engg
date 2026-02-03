import { Send } from "lucide-react";

interface ChatInputBarProps {
  inputValue: string
  setInputValue: (value: string) => void
  isLoading: boolean
  onSendMessage: () => void
  onKeyPress: (e: React.KeyboardEvent) => void
  onOpenPromptModal?: () => void
}

export default function ChatInputBar({
  inputValue,
  setInputValue,
  isLoading,
  onSendMessage,
  onKeyPress,
  onOpenPromptModal
}: ChatInputBarProps) {
  return (
    <div className="fixed bottom-6 left-0 right-0 z-40">
      <div className="mx-auto max-w-6xl px-4">
        {/* Outer glass container */}
        <div className="
          rounded-3xl 
          bg-gradient-to-b from-[#1c2f2f]/80 to-[#0b1515]/80
          backdrop-blur-xl
          border border-white/15
          shadow-[0_20px_60px_rgba(0,0,0,0.6)]
          p-4
        ">
          <div className="flex items-center gap-4">
            {/* Clark icon */}
                <button
                  type="button"
                  onClick={onOpenPromptModal}
              className="
                h-12 w-12 
                rounded-full 
                bg-white/10 
                border border-white/20
                flex items-center justify-center
                hover:bg-white/15
                transition
              "
            >
              <img src="/clark process.svg" alt="Clark" className="h-6 w-6" />
                </button>

            {/* Input */}
            <input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={onKeyPress}
                  placeholder="Ask Clark"
                  disabled={isLoading}
              className="
                flex-1
                h-12
                px-5
                rounded-xl
                bg-white/10
                border border-white/15
                text-white
                placeholder:text-white/60
                focus:outline-none
                focus:ring-1
                focus:ring-white/20
              "
            />

            {/* Send button */}
            <button
                  onClick={onSendMessage}
                  disabled={!inputValue.trim() || isLoading}
              className="
                h-12 w-12
                rounded-xl
                bg-white/15
                border border-white/20
                flex items-center justify-center
                hover:bg-white/25
                transition
                disabled:opacity-40
              "
            >
              <Send className="h-5 w-5 text-white" />
            </button>
              </div>
            </div>
      </div>
    </div>
  )
}
