import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { parseErrorMessage } from "@/lib/parseError";

interface UseWalletKycParams {
  accountData: any;
  setAccountData: (value: any) => void;
}

export function useWalletKyc({ accountData, setAccountData }: UseWalletKycParams) {
  const [kycModalVisible, setKycModalVisible] = useState(false);
  const [kycAccessToken, setKycAccessToken] = useState<string | null>(null);
  const [kycStatus, setKycStatus] = useState<string | null>(null);
  const [kycChecking, setKycChecking] = useState(false);
  const [kycMessage, setKycMessage] = useState<string | null>(null);

  const accountDataRef = useRef(accountData);
  useEffect(() => {
    accountDataRef.current = accountData;
  }, [accountData]);

  const updateKycStatus = useCallback((status: string | null) => {
    setKycStatus(status);
    const current = accountDataRef.current || {};
    const updated = { ...current, kyc_status: status };
    setAccountData(updated);
    localStorage.setItem("userData", JSON.stringify(updated));
  }, [setAccountData]);

  const openKycModal = useCallback(async (userId: string) => {
    if (!userId || kycStatus === "approved") {
      return;
    }
    try {
      await api.post("/api/v1/kyc/applicant", { user_id: userId });
      const tokenRes = await api.post("/api/v1/kyc/access-token", { user_id: userId });
      setKycAccessToken(tokenRes.data.token || tokenRes.data.accessToken || tokenRes.data.access_token);
      setKycModalVisible(true);
    } catch (err) {
      console.error("Failed to open KYC modal:", err);
    }
  }, [kycStatus]);

  const checkKycStatus = useCallback(async (userId: string) => {
    setKycChecking(true);
    setKycMessage(null);

    try {
      const response = await api.post(`/api/v1/kyc/check-status/${userId}`);
      if (response.data.status === "success") {
        const newStatus = response.data.kyc_status || null;
        updateKycStatus(newStatus);

        if (newStatus === "approved") {
          setKycMessage("KYC verification completed successfully!");
          setTimeout(() => setKycMessage(null), 3000);
        } else if (newStatus === "rejected") {
          setKycMessage("KYC verification was rejected. Please try again.");
          setTimeout(() => setKycMessage(null), 5000);
        } else {
          setKycMessage(`KYC status: ${newStatus}`);
          setTimeout(() => setKycMessage(null), 3000);
        }
      } else {
        setKycMessage(response.data.message || "Failed to check KYC status");
        setTimeout(() => setKycMessage(null), 5000);
      }
    } catch (err) {
      console.error("Failed to check KYC status:", err);
      setKycMessage(parseErrorMessage(err, "Failed to check KYC status"));
      setTimeout(() => setKycMessage(null), 5000);
    } finally {
      setKycChecking(false);
    }
  }, [updateKycStatus]);

  const skipKyc = useCallback(async (userId?: string) => {
    try {
      const actualUserId = userId || accountDataRef.current?.id;
      if (!actualUserId) {
        setKycMessage("No user ID found");
        return;
      }
      const response = await api.post(`/api/v1/kyc/skip/${actualUserId}`);
      if (response.data.status === "success") {
        updateKycStatus("approved");
        setKycMessage("KYC skipped successfully");
      } else {
        setKycMessage(response.data.message || "Failed to skip KYC");
      }
    } catch (err) {
      console.error("Failed to skip KYC:", err);
      setKycMessage(parseErrorMessage(err, "Failed to skip KYC"));
    } finally {
      setTimeout(() => setKycMessage(null), 5000);
    }
  }, [updateKycStatus]);

  const pollKycStatus = useCallback(async (userId: string) => {
    for (let i = 0; i < 15; i++) {
      try {
        const res = await api.get(`/api/v1/user/${userId}`);
        const status = res.data.kyc_status || null;

        if (status === "approved") {
          updateKycStatus("approved");
          setKycMessage("KYC verification completed successfully!");
          setTimeout(() => setKycMessage(null), 3000);
          break;
        }
        if (status === "rejected") {
          updateKycStatus("rejected");
          setKycMessage("KYC verification was rejected. Please try again.");
          setTimeout(() => setKycMessage(null), 5000);
          break;
        }

        setKycStatus(status || "pending");
        await new Promise((r) => setTimeout(r, 2000));
      } catch (err) {
        console.error(`Error polling KYC status (attempt ${i + 1}):`, err);
        await new Promise((r) => setTimeout(r, 2000));
      }
    }

    try {
      const finalRes = await api.post(`/api/v1/kyc/check-status/${userId}`);
      if (finalRes.data.status === "success") {
        const finalStatus = finalRes.data.kyc_status || null;
        updateKycStatus(finalStatus);
        if (finalStatus === "approved") {
          setKycMessage("KYC verification completed successfully!");
          setTimeout(() => setKycMessage(null), 3000);
        }
      }
    } catch (err) {
      console.error("Error in final KYC status check:", err);
    }
  }, [updateKycStatus]);

  const handleKycModalClose = useCallback((userId?: string) => {
    setKycModalVisible(false);
    if (userId) {
      checkKycStatus(userId);
      setTimeout(() => {
        pollKycStatus(userId);
      }, 2000);
    }
  }, [checkKycStatus, pollKycStatus]);

  return {
    kycModalVisible,
    kycAccessToken,
    kycStatus,
    kycChecking,
    kycMessage,
    setKycStatus,
    openKycModal,
    checkKycStatus,
    skipKyc,
    handleKycModalClose,
  };
}
