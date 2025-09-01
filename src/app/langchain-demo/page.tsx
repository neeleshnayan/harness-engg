import LangChainChat from '@/components/LangChainChat';

export default function LangChainDemoPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            LangChain Integration Demo
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Experience the power of natural language processing for financial services. 
            Use conversational queries to interact with your backend APIs seamlessly.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          <div className="space-y-4">
            <div className="p-6 border rounded-lg bg-card">
              <h3 className="text-lg font-semibold mb-2">🤖 AI-Powered Parsing</h3>
              <p className="text-sm text-muted-foreground">
                Uses OpenAI's GPT models to understand natural language queries and extract structured information.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-6 border rounded-lg bg-card">
              <h3 className="text-lg font-semibold mb-2">🔗 API Integration</h3>
              <p className="text-sm text-muted-foreground">
                Automatically routes parsed intents to appropriate backend endpoints and executes actions.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-6 border rounded-lg bg-card">
              <h3 className="text-lg font-semibold mb-2">🛡️ Fallback Support</h3>
              <p className="text-sm text-muted-foreground">
                Regex-based parsing when AI parsing fails, ensuring reliability and performance.
              </p>
            </div>
          </div>
        </div>

        <div className="mb-8">
          <div className="p-6 border rounded-lg bg-muted/20">
            <h3 className="text-lg font-semibold mb-4">How It Works</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-center">
              <div className="space-y-2">
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <span className="text-primary font-bold">1</span>
                </div>
                <p className="text-sm font-medium">User Query</p>
                <p className="text-xs text-muted-foreground">Natural language input</p>
              </div>
              
              <div className="space-y-2">
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <span className="text-primary font-bold">2</span>
                </div>
                <p className="text-sm font-medium">AI Parsing</p>
                <p className="text-xs text-muted-foreground">Extract structured data</p>
              </div>
              
              <div className="space-y-2">
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <span className="text-primary font-bold">3</span>
                </div>
                <p className="text-sm font-medium">Intent Recognition</p>
                <p className="text-xs text-muted-foreground">Route to handler</p>
              </div>
              
              <div className="space-y-2">
                <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <span className="text-primary font-bold">4</span>
                </div>
                <p className="text-sm font-medium">Action Execution</p>
                <p className="text-xs text-muted-foreground">Call backend API</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mb-8">
          <div className="p-6 border rounded-lg bg-muted/20">
            <h3 className="text-lg font-semibold mb-4">Supported Actions</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="font-medium text-green-600">✅ Send USDC</h4>
                <p className="text-sm text-muted-foreground">
                  Transfer USDC to other users using natural language
                </p>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>• "Send 100 USDC to Krypton"</p>
                  <p>• "Transfer 50 USDC to Alice"</p>
                  <p>• "Pay 25 USDC to Bob"</p>
                </div>
              </div>
              
              <div className="space-y-2">
                <h4 className="font-medium text-blue-600">✅ Check Balance</h4>
                <p className="text-sm text-muted-foreground">
                  View wallet balance and transaction history
                </p>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>• "Check my balance"</p>
                  <p>• "Show my wallet"</p>
                  <p>• "Get my USDC balance"</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <LangChainChat />
      </div>
    </div>
  );
}
