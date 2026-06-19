'use client';

import { useState, useEffect } from 'react';
import { Music, User } from 'lucide-react';
import Link from 'next/link';

interface TreeNode {
  id: string;
  prompt: string;
  creator: {
    id: string;
    username: string;
  };
  layer_type: string;
  created_at: string;
  children: TreeNode[];
}

interface RemixTreeProps {
  tapeId: string;
}

export default function RemixTree({ tapeId }: RemixTreeProps) {
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set([tapeId]));

  useEffect(() => {
    fetchRemixTree();
  }, [tapeId]);

  const fetchRemixTree = async () => {
    try {
      const response = await fetch(`/api/tapes/${tapeId}/remix-tree`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      const data = await response.json();
      setTreeData(data);
    } catch (error) {
      console.error('Failed to load remix tree:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  const renderNode = (node: TreeNode, level: number = 0) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isCurrentTape = node.id === tapeId;

    return (
      <div key={node.id} className="relative">
        {/* Node */}
        <div
          className={`flex items-start space-x-3 p-4 rounded-lg transition-colors ${
            isCurrentTape
              ? 'bg-[#7c3aed]/20 border-2 border-[#7c3aed]'
              : 'bg-[#2a2a2a] hover:bg-[#333]'
          }`}
          style={{ marginLeft: `${level * 40}px` }}
        >
          {/* Connector Line */}
          {level > 0 && (
            <div className="absolute left-0 top-1/2 w-8 h-0.5 bg-gray-700" style={{ marginLeft: `${(level - 1) * 40 + 20}px` }} />
          )}

          {/* Expand/Collapse Button */}
          {hasChildren && (
            <button
              onClick={() => toggleNode(node.id)}
              className="flex-shrink-0 w-6 h-6 rounded-full bg-[#7c3aed] flex items-center justify-center text-white text-xs font-bold hover:bg-[#6d28d9] transition-colors"
            >
              {isExpanded ? '−' : '+'}
            </button>
          )}

          {/* Node Icon */}
          <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-[#7c3aed] to-[#ec4899] rounded-lg flex items-center justify-center">
            <Music className="w-6 h-6 text-white" />
          </div>

          {/* Node Content */}
          <div className="flex-1 min-w-0">
            <Link
              href={`/tape/${node.id}`}
              className="text-white font-medium hover:text-[#7c3aed] transition-colors line-clamp-1"
            >
              {node.prompt}
            </Link>
            
            <div className="flex items-center space-x-3 mt-1 text-sm">
              <Link
                href={`/profile/${node.creator.id}`}
                className="flex items-center space-x-1 text-gray-400 hover:text-white transition-colors"
              >
                <User className="w-3 h-3" />
                <span>{node.creator.username}</span>
              </Link>
              
              <span className="text-gray-500">•</span>
              
              <span className="text-gray-400 capitalize">{node.layer_type}</span>
              
              <span className="text-gray-500">•</span>
              
              <span className="text-gray-400">
                {new Date(node.created_at).toLocaleDateString()}
              </span>
            </div>

            {hasChildren && (
              <div className="mt-2 text-xs text-gray-500">
                {node.children.length} remix{node.children.length !== 1 ? 'es' : ''}
              </div>
            )}
          </div>

          {/* Current Indicator */}
          {isCurrentTape && (
            <div className="flex-shrink-0 px-2 py-1 bg-[#7c3aed] text-white text-xs font-bold rounded">
              YOU ARE HERE
            </div>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className="mt-2 space-y-2">
            {node.children.map(child => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#7c3aed]"></div>
      </div>
    );
  }

  if (!treeData) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Music className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>No remix tree available</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex items-center space-x-4 mb-6 text-sm text-gray-400">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-[#7c3aed] rounded"></div>
          <span>Current tape</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-[#2a2a2a] rounded"></div>
          <span>Related tapes</span>
        </div>
      </div>

      {/* Tree */}
      <div className="space-y-2">
        {renderNode(treeData)}
      </div>

      {/* Stats */}
      <div className="mt-6 pt-6 border-t border-gray-800">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-white">
              {countNodes(treeData)}
            </div>
            <div className="text-sm text-gray-400">Total Tapes</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {getMaxDepth(treeData)}
            </div>
            <div className="text-sm text-gray-400">Max Depth</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">
              {countLeaves(treeData)}
            </div>
            <div className="text-sm text-gray-400">Leaf Nodes</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Helper functions
function countNodes(node: TreeNode | null): number {
  if (!node) return 0;
  return 1 + (node.children?.reduce((sum, child) => sum + countNodes(child), 0) || 0);
}

function getMaxDepth(node: TreeNode | null, depth: number = 0): number {
  if (!node) return depth;
  if (!node.children || node.children.length === 0) return depth + 1;
  return Math.max(...node.children.map(child => getMaxDepth(child, depth + 1)));
}

function countLeaves(node: TreeNode | null): number {
  if (!node) return 0;
  if (!node.children || node.children.length === 0) return 1;
  return node.children.reduce((sum, child) => sum + countLeaves(child), 0);
}
