import { QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api";
export function createQueryClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (error instanceof ApiError && [403, 404].includes(error.status)) {
          // Po odvolání práv nezůstane stará úspěšná odpověď ve vadném query.
          query.setState({ data: undefined, dataUpdatedAt: 0 });
        }
      },
    }),
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: "always", gcTime: 0 },
      mutations: { retry: false, gcTime: 0 },
    },
  });
}
