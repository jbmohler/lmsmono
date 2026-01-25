/**
 * Journal domain models matching backend /api/journals endpoints.
 */

/** Journal entity */
export interface Journal {
  id: string;
  jrn_name: string;
  description: string | null;
}

/** Data for creating a new journal */
export interface JournalCreate {
  jrn_name: string;
  description?: string | null;
}

/** Data for updating a journal (all fields optional) */
export interface JournalUpdate {
  jrn_name?: string;
  description?: string | null;
}
