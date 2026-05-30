import { Component, computed, input, output } from '@angular/core';

export interface TagNode {
  id: string;
  name: string;
  parentId?: string | null;
  description?: string;
}

interface TreeNode extends TagNode {
  children: TreeNode[];
  depth: number;
}

@Component({
  selector: 'app-tag-selector',
  templateUrl: './tag-selector.component.html',
  styleUrl: './tag-selector.component.scss',
  imports: [],
})
export class TagSelectorComponent {
  allTags = input.required<TagNode[]>();
  selectedIds = input.required<string[]>();
  disabled = input(false);
  mode = input<'tree' | 'flat'>('flat');

  tagToggled = output<{ tagIds: string[]; action: 'add' | 'remove' }>();

  private selectedSet = computed(() => new Set(this.selectedIds()));

  /** Build a depth-ordered flat list suitable for rendering the tree. */
  treeNodes = computed<TreeNode[]>(() => {
    const tags = this.allTags();
    const nodeMap = new Map<string, TreeNode>();
    for (const t of tags) {
      nodeMap.set(t.id, { ...t, children: [], depth: 0 });
    }
    const roots: TreeNode[] = [];
    for (const node of nodeMap.values()) {
      if (node.parentId && nodeMap.has(node.parentId)) {
        nodeMap.get(node.parentId)!.children.push(node);
      } else {
        roots.push(node);
      }
    }

    const result: TreeNode[] = [];
    const visit = (nodes: TreeNode[], depth: number): void => {
      nodes.sort((a, b) => a.name.localeCompare(b.name));
      for (const n of nodes) {
        n.depth = depth;
        result.push(n);
        visit(n.children, depth + 1);
      }
    };
    visit(roots, 0);
    return result;
  });

  /** Flat sorted list for flat mode. */
  flatNodes = computed(() =>
    [...this.allTags()].sort((a, b) => a.name.localeCompare(b.name))
  );

  isSelected(id: string): boolean {
    return this.selectedSet().has(id);
  }

  toggle(node: TagNode): void {
    if (this.disabled()) return;
    if (this.isSelected(node.id)) {
      // Unchecking: cascade — also remove all selected descendants to preserve the invariant
      // that no child can be selected without its ancestors.
      const treeNode = this.treeNodes().find(n => n.id === node.id);
      const toRemove = treeNode ? this.collectSelected(treeNode) : [node.id];
      this.tagToggled.emit({ tagIds: toRemove, action: 'remove' });
    } else {
      this.tagToggled.emit({ tagIds: [node.id], action: 'add' });
    }
  }

  private collectSelected(node: TreeNode): string[] {
    const sel = this.selectedSet();
    const result: string[] = [];
    if (sel.has(node.id)) result.push(node.id);
    for (const child of node.children) {
      result.push(...this.collectSelected(child));
    }
    return result;
  }
}
