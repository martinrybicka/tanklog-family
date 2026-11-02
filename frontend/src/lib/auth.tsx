import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import type { Session } from "./types";

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      try {
        return (await api<Session>("auth/me/")).data;
      } catch (error) {
        if (
          error instanceof ApiError &&
          error.code === "authentication_required"
        )
          return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 30_000,
  });
}
