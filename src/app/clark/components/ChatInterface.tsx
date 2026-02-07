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
    <div
      className="
        fixed bottom-0 left-0 right-0 z-40
        backdrop-blur-xl
      "
    >
      <div className="mx-auto max-w-6xl px-3 sm:px-6 lg:px-8">
        <div
          className="
            rounded-t-3xl 
            shadow-[0_-10px_40px_rgba(0,0,0,0.6)]
            px-3 sm:px-4 py-2
          "
          style={{
            background:
              "linear-gradient(180deg, rgba(255, 255, 255, 0.36) 0%, rgba(161, 207, 211, 0.12) 100%)",
          }}
        >
          <div className="flex items-center gap-2 sm:gap-4">
            {/* Clark icon - type="button" so it never submits a form */}
            <button
              type="button"
              onClick={onOpenPromptModal}
              className="
                h-10 w-10 sm:h-12 sm:w-12
                rounded-full 
                bg-white/10 
                border border-white/20
                flex items-center justify-center
                hover:bg-white/15
                transition
              "
            >
              <img src="/clark process.svg" alt="Clark" className="h-5 w-5 sm:h-6 sm:w-6" />
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
                h-10 sm:h-12
                px-3 sm:px-5
                rounded-xl
                bg-white/10
                border border-white/15
                text-sm sm:text-base
                text-white
                placeholder:text-white/60
                focus:outline-none
                focus:ring-1
                focus:ring-white/20
              "
            />

            {/* Send button - type="button" so it never submits a form; image has pointer-events-none so click hits the button */}
            <button
              type="button"
              onClick={() => onSendMessage()}
              disabled={!inputValue.trim() || isLoading}
              className="flex items-center justify-center h-10 w-10 sm:h-12 sm:w-12"
            >
              <img src="/send button.svg" alt="Send" className="h-7 w-7 sm:h-10 sm:w-10 pointer-events-none" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
