export function artifactLink(value,assetUrl,isImage=false) {
 if(!value)return '';
 if(value.startsWith('#'))return isImage?'':value;
 if(/^(https?:|mailto:)/i.test(value))return isImage?'':value;
 if(/^[a-z][a-z0-9+.-]*:|^[\/\\]/i.test(value))return '';
 return assetUrl+'/asset?path='+encodeURIComponent(value);
}
