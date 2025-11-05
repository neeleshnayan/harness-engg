type Step = {
  label: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
};

type TransactionProgressBarProps = {
  steps: Step[];
};

export const TransactionProgressBar = ({ steps }: TransactionProgressBarProps) => {
  const getStepIcon = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return (
          <svg className="h-4 w-4 text-green-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        );
      case 'active':
        return (
          <svg className="h-4 w-4 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        );
      case 'failed':
        return (
          <svg className="h-4 w-4 text-red-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        );
      default:
        return (
          <div className="h-4 w-4 rounded-full border-2 border-white/30"></div>
        );
    }
  };

  const getStepColor = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'active':
        return 'bg-blue-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-white/20';
    }
  };

  const getStepTextColor = (status: Step['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-300';
      case 'active':
        return 'text-blue-300 font-medium';
      case 'failed':
        return 'text-red-300';
      default:
        return 'text-white/50';
    }
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={index} className="flex items-center flex-1">
            {/* Step Circle */}
            <div className="flex flex-col items-center">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full ${
                step.status === 'pending' ? 'bg-white/10' : getStepColor(step.status)
              }`}>
                {getStepIcon(step.status)}
              </div>
              <p className={`mt-2 text-xs ${getStepTextColor(step.status)}`}>
                {step.label}
              </p>
            </div>

            {/* Connector Line */}
            {index < steps.length - 1 && (
              <div className="flex-1 mx-2">
                <div className="h-0.5 bg-white/20 relative overflow-hidden">
                  {(step.status === 'completed' || steps[index + 1].status === 'active' || steps[index + 1].status === 'completed') && (
                    <div className="absolute inset-0 bg-gradient-to-r from-green-500 to-blue-500 animate-pulse"></div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
