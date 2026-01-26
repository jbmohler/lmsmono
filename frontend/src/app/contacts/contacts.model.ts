export interface ContactBitBase {
  id: string;
  bitType: 'email' | 'phone' | 'address' | 'url';
  label: string;
  memo: string;
  isPrimary: boolean;
  bitSequence: number;
}

export interface ContactEmail extends ContactBitBase {
  bitType: 'email';
  email: string;
}

export interface ContactPhone extends ContactBitBase {
  bitType: 'phone';
  number: string;
}

export interface ContactAddress extends ContactBitBase {
  bitType: 'address';
  address1: string;
  address2: string;
  city: string;
  state: string;
  zip: string;
  country: string;
}

export interface ContactUrl extends ContactBitBase {
  bitType: 'url';
  url: string;
  username: string;
  hasPassword: boolean;
  pwResetDt: string | null;
  pwNextResetDt: string | null;
}

export type ContactBit = ContactEmail | ContactPhone | ContactAddress | ContactUrl;

export interface Persona {
  id: string;
  firstName: string;
  lastName: string;
  title: string;
  organization: string;
  memo: string;
  birthday: string | null;
  anniversary: string | null;
  isCorporate: boolean;
  bits: ContactBit[];
}
