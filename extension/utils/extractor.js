// extension/utils/extractor.js
const SELECTORS = {
  FEED_POST: 'div[data-urn*="urn:li:activity"]',
  POST_CONTENT: '.feed-shared-update-v2__description, .update-components-text',
  AUTHOR_NAME: '.update-components-actor__name, .feed-shared-actor__name',
  AUTHOR_HEADLINE: '.update-components-actor__description, .feed-shared-actor__description',
  AUTHOR_PROFILE_LINK: '.update-components-actor__meta a, .feed-shared-actor__meta a',
  DEGREE_BADGE: '.dist-value',
  LIKE_COUNT: '.social-details-social-counts__reactions-count',
  COMMENT_COUNT: '.social-details-social-counts__comments',
  POST_TIMESTAMP: '.update-components-actor__sub-description time',
};

const EXTRACTION_VERSION = '1.0.0';

function extractDegree(postElement) {
  const badge = postElement.querySelector(SELECTORS.DEGREE_BADGE);
  if (!badge) return 3;
  const text = badge.textContent.trim();
  if (text.includes('1st')) return 1;
  if (text.includes('2nd')) return 2;
  return 3;
}

function extractLinkedInId(profileUrl) {
  if (!profileUrl) return null;
  const match = profileUrl.match(/linkedin\.com\/in\/([^/?]+)/);
  return match ? match[1] : null;
}

function extractPost(postElement) {
  const urn = postElement.getAttribute('data-urn');
  if (!urn) return null;

  const content = postElement.querySelector(SELECTORS.POST_CONTENT)?.textContent?.trim();
  if (!content || content.length < 20) return null;

  const authorName = postElement.querySelector(SELECTORS.AUTHOR_NAME)?.textContent?.trim();
  if (!authorName) return null;

  const profileLink = postElement.querySelector(SELECTORS.AUTHOR_PROFILE_LINK)?.href;
  const linkedinId = extractLinkedInId(profileLink) || authorName.toLowerCase().replace(/\s+/g, '');

  const headline = postElement.querySelector(SELECTORS.AUTHOR_HEADLINE)?.textContent?.trim() || '';
  const degree = extractDegree(postElement);

  const timestampEl = postElement.querySelector(SELECTORS.POST_TIMESTAMP);
  const postedAt = timestampEl?.getAttribute('datetime') || null;

  const likes = parseInt(postElement.querySelector(SELECTORS.LIKE_COUNT)?.textContent?.replace(/[^0-9]/g, '') || '0');
  const comments = parseInt(postElement.querySelector(SELECTORS.COMMENT_COUNT)?.textContent?.replace(/[^0-9]/g, '') || '0');

  return {
    linkedin_post_id: urn,
    author: {
      name: authorName,
      headline: headline,
      profile_url: profileLink || null,
      linkedin_id: linkedinId,
      degree: degree,
    },
    content: content,
    post_type: 'post',
    posted_at: postedAt,
    engagement: { likes, comments },
    extraction_version: EXTRACTION_VERSION,
    captured_at: new Date().toISOString(),
  };
}

function extractVisiblePosts() {
  const postElements = document.querySelectorAll(SELECTORS.FEED_POST);
  const posts = [];

  for (const el of postElements) {
    try {
      const post = extractPost(el);
      if (post) posts.push(post);
    } catch (e) {
      console.warn('[Sonar] Failed to extract post:', e.message);
    }
  }

  return posts;
}
