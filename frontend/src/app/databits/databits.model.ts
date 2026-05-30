export interface DataBitTag {
  id: string;
  name: string;
  description: string;
}

export interface DataBit {
  id: string;
  caption: string;
  data: string;
  website: string;
  uname: string;
  pword: string;
  tags: DataBitTag[];
}

export interface DataBitListItem {
  id: string;
  caption: string;
  website: string;
  uname: string;
}
