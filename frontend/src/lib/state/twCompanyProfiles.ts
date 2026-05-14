import { fetchTwCompanyProfiles } from "../api";
import type { TwCompanyProfile } from "../types";

let cachedProfiles: TwCompanyProfile[] | null = null;
let inFlightProfiles: Promise<TwCompanyProfile[]> | null = null;

export const loadTwCompanyProfiles = async () => {
  if (cachedProfiles) {
    return cachedProfiles;
  }

  inFlightProfiles = inFlightProfiles ?? fetchTwCompanyProfiles();
  try {
    cachedProfiles = await inFlightProfiles;
    return cachedProfiles;
  } catch (error) {
    inFlightProfiles = null;
    throw error;
  }
};
