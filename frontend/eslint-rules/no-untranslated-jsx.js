/**
 * no-untranslated-jsx — catches raw string literals in assistive-tech / document-metadata
 * JSX props that react/jsx-no-literals does not cover by default.
 *
 * Fails on: aria-label, aria-describedby, aria-placeholder, aria-roledescription,
 *   aria-valuetext, alt, title (on any element), placeholder.
 *
 * Allowed via E1-E6 exemptions (escape hatch):
 *   // i18n-allowlisted: <reason>  on the preceding line.
 */

const PROP_LIST = new Set([
  'aria-label', 'aria-describedby', 'aria-placeholder',
  'aria-roledescription', 'aria-valuetext',
  'alt', 'title', 'placeholder',
]);

// content is only translatable on <meta> elements
const META_ONLY_PROPS = new Set(['content']);

function isStringLiteral(node) {
  return node && node.type === 'Literal' && typeof node.value === 'string' && node.value.trim().length > 0;
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow raw string literals in translatable JSX props',
      recommended: false,
    },
    schema: [],
  },
  create(context) {
    return {
      JSXAttribute(node) {
        const propName = node.name?.name;
        if (!propName) return;
        const parentElementName = node.parent?.name?.name;
        const isTranslatable =
          PROP_LIST.has(propName) ||
          (META_ONLY_PROPS.has(propName) && parentElementName === 'meta');
        if (!isTranslatable) return;
        const value = node.value;
        if (!value) return;

        let stringNode = null;
        if (isStringLiteral(value)) {
          stringNode = value;
        } else if (
          value.type === 'JSXExpressionContainer' &&
          isStringLiteral(value.expression)
        ) {
          stringNode = value.expression;
        }

        if (!stringNode) return;

        const commentsBefore = context.sourceCode.getCommentsBefore(node);
        const hasAllowlist = commentsBefore.some((c) =>
          c.value.includes('i18n-allowlisted'),
        );
        if (hasAllowlist) return;

        context.report({
          node: stringNode,
          message: `Raw string literal in '${propName}' prop. Route through i18n.ts using t(). Add // i18n-allowlisted: <reason> to suppress for non-translatable values.`,
        });
      },
    };
  },
};
