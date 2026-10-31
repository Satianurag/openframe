import { useEffect, useRef, useState } from 'react';
import { mediaUrl, post, upload } from '../api';
import { Icon } from '../Icon';
import { AnchoredPopover } from '../Popovers';
import type { Asset, Job } from '../types';
import { AppSwitcher } from './AppSwitcher';
import { SequencePlanner } from './SequencePlanner';
import { useAppDocument } from './useAppDocument';
import { loadProjectSnapshot, missingProjectSnapshot, projectReuseDescription, showProjectDraft } from './projectReuse';
import { modelProviderIssue, providerReadinessIssue, renderRequest, renderSize, resolveProvider } from './renderRequest';
import { AssetPicker, boundedVideoFrames, importReference, ReferenceDialog, ReferenceMedia, ResultDialog, SourceSlot, useReferenceLibrary, useWorkspaceAssets, WorkspaceDialog, WorkspaceHistory } from './engine-apps-shared';
import type { EngineAppProps, ReferenceItem } from './engine-apps-shared';
import './engine-apps.css';

type MarketingState = { attachment_asset_ids?:string[]; finishing_video_asset_id?:string; finishing_audio_asset_id?:string; speech_model_id?:string; image_model_id?:string; video_model_id?:string; prompt:string; mode:'image'|'video'; product_asset_id:string; avatar_asset_id:string; template_asset_id:string; composition_asset_id:string; extra_asset_id:string; ad_asset_id:string; ad_trim:number; template:string; framing:string; style_category:string; aspect_ratio:string; variants:number; duration:number; provider:string; narration:string; voice:string; product_url:string; product_name:string; product_description:string };
const initial:MarketingState={speech_model_id:'ming-narration',image_model_id:'flux3-klein',video_model_id:'ltx-2.5',prompt:'',mode:'image',product_asset_id:'',avatar_asset_id:'',template_asset_id:'',composition_asset_id:'',extra_asset_id:'',ad_asset_id:'',ad_trim:0,template:'',framing:'Closeup',style_category:'Product shot',aspect_ratio:'3:4',variants:1,duration:5,provider:'',narration:'',voice:'US_Emma',product_url:'',product_name:'',product_description:''};
const assetIds=(state:MarketingState)=>[state.product_asset_id,state.avatar_asset_id,state.template_asset_id,state.composition_asset_id,state.extra_asset_id,state.ad_asset_id,state.finishing_video_asset_id||'',state.finishing_audio_asset_id||'',...(state.attachment_asset_ids||[])].filter(Boolean);
const categories=['All','Product shot','Motion','UGC','TikTok','Ads','Posters','Marketplace'];
const videoCategories=['UGC','Motion','TikTok'];

export function MarketingAds({catalog,settings,onSettings}:EngineAppProps){
  const session=useAppDocument('marketing-ads',initial,assetIds),{state,update}=session;
  const assets=useWorkspaceAssets(assetIds(state)),library=useReferenceLibrary('marketing-ads');
  const [view,setView]=useState<'Home'|'Projects'|'Favorites'>('Home'),[expanded,setExpanded]=useState(false);
  const [category,setCategory]=useState('All'),[kind,setKind]=useState('All'),[carousel,setCarousel]=useState(1);
  const [picker,setPicker]=useState<'product'|'avatar'|'extra'|'ad'|'finish'|null>(null),[panel,setPanel]=useState<'styles'|'ad'|'link'|null>(null);
  const [styleCategory,setStyleCategory]=useState('Product shot'),[search,setSearch]=useState('');
  const [preview,setPreview]=useState<ReferenceItem|null>(null),[selected,setSelected]=useState<Job|null>(null);
  const [voiceover,setVoiceover]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [menu,setMenu]=useState<{name:'Aspect ratio'|'Duration';anchor:HTMLElement}|null>(null);
  const [link,setLink]=useState(''),[importWarnings,setImportWarnings]=useState<string[]>([]);
  const productFile=useRef<HTMLInputElement>(null);
  const [finishing,setFinishing]=useState(false);
  const finishingVideo=assets.get(state.finishing_video_asset_id||'');
  useEffect(()=>{if(!library.hero?.length||matchMedia('(prefers-reduced-motion: reduce)').matches)return;const timer=setInterval(()=>setCarousel(value=>(value+1)%library.hero!.length),6500);return()=>clearInterval(timer);},[library.hero?.length]);
  const provider=resolveProvider(state.provider, settings.default_provider);
  const providerIssue=providerReadinessIssue(catalog.providers.find(item=>item.id===provider));
  const speechModels=catalog.models.filter(item=>catalog.effects.find(effect=>effect.id==='generate-speech')?.model_ids.includes(item.id));
  const speechModelId=state.speech_model_id||'ming-narration';
  const speechModel=speechModels.find(item=>item.id===speechModelId);
  const speechVoices=(speechModel?.voices as {id:string;name:string}[]|undefined)||[];
  const speechVoice=speechVoices.find(item=>item.id===state.voice)?.id||(!state.speech_model_id?speechVoices[0]?.id:'')||'';
  const speechLimit=Number(speechModel?.max_script_characters||1200);
  const speechIssue=!speechModel?'The selected speech model is unavailable in the current catalog. Reload after the service update or explicitly choose another model.':!speechVoice?'Choose a supported voice for this model.':providerIssue||modelProviderIssue(speechModel,provider)|| (state.narration.length>speechLimit?`This model accepts up to ${speechLimit} script characters.`:'');

  const references=[state.product_asset_id,state.avatar_asset_id,state.template_asset_id,state.extra_asset_id].filter(Boolean);
  const needsComposition=state.mode==='video'&&references.length>1&&!state.composition_asset_id;
  const generatingImage=state.mode==='image'||needsComposition;
  const effectId=generatingImage?(references.length?'edit-image':'create-image'):state.ad_asset_id?'restyle':'product-reveal';
  const model=catalog.models.find(item=>item.id===(generatingImage?(state.image_model_id||'flux-klein-4b'):state.ad_asset_id?'wan-vace':(state.video_model_id||'ltx-2.3')));
  const product=assets.get(state.product_asset_id),avatar=assets.get(state.avatar_asset_id),ad=assets.get(state.ad_asset_id);
  const templates=(library.presets||[]).filter(item=>(category==='All'||item.category===category)&&(kind==='All'||(kind==='Videos'?!!item.video:!item.video)));
  const styleItems=(library.styles||[]).filter(item=>item.category===styleCategory&&item.title.toLowerCase().includes(search.toLowerCase()));
  const visibleHero=library.hero?.length?[-2,-1,0,1,2].map(offset=>library.hero![(carousel+offset+library.hero!.length)%library.hero!.length]):[];
  const videoFrames=model?boundedVideoFrames(model,state.duration,ad,state.ad_trim||0):0;

  function openStyles(value=state.style_category||'Product shot'){setStyleCategory(value);setSearch('');setPanel('styles');}
  async function chooseStyle(item:ReferenceItem){
    setBusy(true);setError('');
    try{const asset=await importReference(item,'image');assets.add(asset);update({framing:item.title,style_category:item.category||'Product shot',template:item.title,template_asset_id:asset.id,composition_asset_id:'',mode:videoCategories.includes(item.category||'')?'video':'image'});setPanel(null);}
    catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function useTemplate(item:ReferenceItem){
    setBusy(true);setError('');
    try{const asset=await importReference(item,'image');assets.add(asset);update({template:item.title,template_asset_id:asset.id,composition_asset_id:'',style_category:item.category||'Product shot',framing:item.title,mode:item.video?'video':'image',prompt:item.prompt||`Create a polished ${item.category||'product'} composition inspired by the ${item.title} reference. Keep the supplied product recognizable and the scene visually coherent.`});setPreview(null);}
    catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function importProduct(){
    setBusy(true);setError('');setImportWarnings([]);
    try{const value=await post<{title:string;description:string;source_url:string;asset:Asset;warnings:string[]}>('/import/product',{url:link.includes('://')?link.trim():`https://${link.trim()}`});assets.add(value.asset);update({product_asset_id:value.asset.id,product_name:value.title,product_description:value.description,product_url:value.source_url,composition_asset_id:''});setImportWarnings(value.warnings);}
    catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function manualProduct(file?:File){
    if(!file)return;setBusy(true);setError('');
    try{const asset=await upload(file);if(asset.kind!=='image')throw new Error('Choose a product image.');assets.add(asset);update({product_asset_id:asset.id,product_name:asset.name,product_description:'',product_url:'',composition_asset_id:''});}
    catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function generate(utility?:'remove-background'|'generate-speech'){
    setBusy(true);setError('');
    try{
      if(providerIssue)throw new Error(providerIssue);
      const operationId=utility||effectId;
      const selectedModel=utility==='generate-speech'?speechModel:utility?catalog.models.find(item=>item.id==='birefnet'):model;
      const operation=session.application?.operations.find(item=>item.id===operationId);
      if(!selectedModel||!operation?.available)throw new Error(operation?.reason||'The selected operation is not available.');
      if(provider==='comfy-cloud'&&!['restyle','product-reveal'].includes(operationId))throw new Error('Choose a supported local ComfyUI connection for this workflow.');
      if(utility==='remove-background'&&!product)throw new Error('Choose a product image first.');
      if(utility==='generate-speech'&&!state.narration.trim())throw new Error('Write a voiceover script first.');
      if(utility==='generate-speech'&&speechIssue)throw new Error(speechIssue);
      if(!utility&&!state.prompt.trim()&&!references.length&&!state.composition_asset_id)throw new Error('Add a product or describe the scene you want to create.');
      if(!utility&&!generatingImage&&!state.ad_asset_id&&!state.composition_asset_id&&!references.length)throw new Error('Choose a product image before animating it.');
      if(!utility&&!generatingImage&&videoFrames<9)throw new Error('Choose a longer source video interval.');
      const document=utility==='generate-speech'?await session.updateAndSave({speech_model_id:selectedModel.id,voice:speechVoice}):await session.save(true);if(!document)throw new Error('Save this project before generating.');
      const direction=state.prompt.trim()||`Create a polished ${state.style_category||'product shot'} featuring the supplied product. Natural lighting, coherent detail and a visually clear composition.`;
      const prompt=utility==='generate-speech'?state.narration:utility==='remove-background'?'Extract the product foreground with a transparent background.':`${direction}\nVisual direction: ${state.framing}. ${generatingImage&&state.avatar_asset_id?'Use the avatar reference for the person and preserve the supplied product appearance.':''}${state.product_name?`\nProduct: ${state.product_name}. ${state.product_description||''}`:''}`;
      const source=utility==='remove-background'?state.product_asset_id:utility?undefined:generatingImage?references[0]:state.ad_asset_id||state.composition_asset_id||references[0];
      const request=renderRequest(selectedModel,{effect_id:operationId,prompt,provider,...renderSize(selectedModel,state.aspect_ratio,utility?512:1024),frames:utility||generatingImage?1:videoFrames,fps:utility||generatingImage?1:Number(selectedModel.default_fps||24),source_asset_id:source,reference_asset_ids:!utility&&generatingImage?references.slice(1):[],reference_asset_id:!utility&&!generatingImage&&state.ad_asset_id?(state.composition_asset_id||references[0]):undefined,trim_start:!generatingImage&&state.ad_asset_id?state.ad_trim||0:0,batch_size:utility||!generatingImage?1:state.variants,voice:utility==='generate-speech'?speechVoice:state.voice,caption_language:utility==='generate-speech'&&speechVoices.find(item=>item.id===speechVoice)?.name.includes('Chinese')?'Chinese':'English',speech_speed:1,strength:state.ad_asset_id?0.4:1});
      const job=await post<Job>(`/apps/marketing-ads/documents/${document.id}/jobs`,{expected_revision:document.revision,operation:operationId,request,step_id:needsComposition&&!utility?'compose':utility||state.mode});setSelected(job);await session.refreshJobs();
    }catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function reuseProject(job: Job) {
    setBusy(true); setError(''); setView('Home');
    try {
      const snapshot = await loadProjectSnapshot<MarketingState>(job, 'marketing-ads', catalog, assetIds);
      if (!['image', 'video'].includes(snapshot.state.mode)) throw new Error(missingProjectSnapshot);
      const next = { ...initial, ...snapshot.state, title: snapshot.title, provider: job.request.provider };
      const operation = job.request.effect_id;
      if (['create-image', 'edit-image'].includes(operation)) next.image_model_id = job.request.model_id;
      else if (operation === 'product-reveal') next.video_model_id = job.request.model_id;
      else if (operation === 'generate-speech') { next.speech_model_id = job.request.model_id; next.voice = job.request.voice || snapshot.state.voice; next.narration = job.request.prompt; }
      else {
        const fixedModels: Record<string, string> = { restyle: 'wan-vace', 'remove-background': 'birefnet' };
        if (fixedModels[operation] !== job.request.model_id)
          throw new Error('This recorded workflow cannot be restored by Ads Studio. No model was substituted; use its workflow export.');
      }
      if (!await session.newDocument(next)) return;
      const draft = await session.save(true);
      if (!draft) throw new Error('The reused project could not be saved.');
      showProjectDraft(draft.id, '/marketing-studio');
      setVoiceover(operation === 'generate-speech');
      setPanel(null); setPreview(null); setMenu(null);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }
  async function openFinishing(asset:Asset){
    if(asset.kind!=='video'||!asset.frame_count||!asset.fps||!asset.width||!asset.height){setError('Select a video with complete frame and geometry metadata.');return;}
    assets.add(asset);setBusy(true);setError('');
    try{const doc=await session.updateAndSave({finishing_video_asset_id:asset.id});if(!doc)throw new Error('Save the selected video before assembly.');setSelected(null);setFinishing(true);}
    catch(reason){setError((reason as Error).message);}finally{setBusy(false);}
  }
  async function useResult(asset:Asset){
    if(asset.kind==='video'){await openFinishing(asset);return;}
    assets.add(asset);
    if(asset.kind==='audio'){
      const doc=await session.updateAndSave({finishing_audio_asset_id:asset.id});
      if(!doc){setError('Save the recording before using it as voiceover.');return;}
      setSelected(null);if(finishingVideo)await openFinishing(finishingVideo);else setPicker('finish');
    }else update({composition_asset_id:asset.id,mode:'video'});
    setView('Home');
  }
  function selectAsset(asset:Asset){
    if(picker==='finish'){setPicker(null);void openFinishing(asset);return;}
    if(picker==='ad')update({ad_asset_id:asset.id,ad_trim:0,mode:'video'});
    else if(picker==='avatar')update({avatar_asset_id:asset.id,composition_asset_id:''});
    else if(picker==='extra')update({extra_asset_id:asset.id,composition_asset_id:''});
    else update({product_asset_id:asset.id,product_name:asset.name,product_description:'',product_url:'',composition_asset_id:''});
  }
  const failure=error||session.error||assets.error;
  return <main className={`marketing-app ea-app ${expanded?'expanded':''}`}>
    <aside className="marketing-rail"><div className="marketing-rail-top"><AppSwitcher name="Marketing Studio"/><button aria-label={expanded?'Collapse sidebar':'Expand sidebar'} onClick={()=>setExpanded(!expanded)}><Icon name="split"/></button></div><button className={view==='Home'?'active':''} onClick={()=>setView('Home')} aria-label="Marketing home"><Icon name="grid"/><span>Home</span></button><button className="rail-avatar" onClick={()=>setView('Projects')} aria-label="My generations"><Icon name="spark"/><span>My generations</span></button><button className="rail-product" onClick={()=>setView('Favorites')} aria-label="My favorites"><Icon name="heart"/><span>My favorites</span></button><small>Tools</small><button onClick={()=>setPanel('ad')} aria-label="Ad Reference"><Icon name="image"/><span>Ad Reference</span></button><button onClick={()=>{setLink(state.product_url||'');setPanel('link');}} aria-label="Product Link"><Icon name="external"/><span>Product Link</span></button><small>Projects</small><button onClick={()=>{void session.newDocument();setView('Home');}} aria-label="New project"><Icon name="plus"/><span>New project</span></button><i/><button className={view==='Projects'?'active':''} onClick={()=>setView('Projects')} aria-label="All projects"><Icon name="folder"/><span>All projects</span></button><button onClick={onSettings} aria-label="Compute settings"><Icon name="settings"/><span>Compute settings</span></button></aside>
    <section className="marketing-workspace"><div className="marketing-topline"><span>MARKETING STUDIO</span><button onClick={()=>setView(view==='Projects'?'Home':'Projects')}>{view==='Projects'?'Create':'Projects'}<Icon name="folder" size={14}/></button></div>
    {view==='Home'?<><section className="marketing-hero"><div className="marketing-hero-cards">{visibleHero.map((item,index)=><button key={item.id||index} className={`card-${index}`} onClick={()=>{if(item.title==='Posters')update({mode:'image',style_category:'Posters',framing:'Poster'});else openStyles(item.category||item.title);}}><ReferenceMedia item={item}/><span>{item.category||item.title}</span></button>)}</div><h1>TURN ANY PRODUCT<br/>INTO READY TO POST CONTENT</h1></section>
      <section className="marketing-composer"><div className="marketing-mode" role="tablist" aria-label="Output type">{(['image','video'] as const).map(mode=><button role="tab" aria-selected={state.mode===mode} className={state.mode===mode?'active':''} key={mode} onClick={()=>update({mode})}><Icon name={mode} size={16}/>{mode==='image'?'Image':'Video'}</button>)}</div><div className="marketing-compose-box"><div className="marketing-prompt"><textarea aria-label="Describe your marketing scene" placeholder={state.composition_asset_id&&state.mode==='video'?'Describe how your composition should move…':'Describe what you want to create…'} value={state.prompt} onChange={event=>update({prompt:event.target.value})}/><div className="marketing-inline-controls"><button onClick={()=>setPicker('extra')} aria-label="Add reference image"><Icon name="plus" size={16}/></button><button onClick={()=>openStyles()} aria-label="Choose style">{state.framing}<Icon name="down" size={11}/></button><button onClick={event=>setMenu({name:'Aspect ratio',anchor:event.currentTarget})} aria-label={`Aspect ratio: ${state.aspect_ratio}`}><Icon name="square" size={13}/>{state.aspect_ratio}</button>{state.mode==='image'?<span className="marketing-variants"><button aria-label="Decrease batch size" disabled={state.variants===1} onClick={()=>update({variants:state.variants-1})}>−</button>{state.variants}/4<button aria-label="Increase batch size" disabled={state.variants===4} onClick={()=>update({variants:state.variants+1})}>+</button></span>:<button onClick={event=>setMenu({name:'Duration',anchor:event.currentTarget})}>{state.duration}s<Icon name="down" size={11}/></button>}</div></div><SourceSlot compact title="Avatar" asset={avatar} onChoose={()=>setPicker('avatar')} onClear={()=>update({avatar_asset_id:'',composition_asset_id:''})}/><SourceSlot compact title="Product" asset={product} onChoose={()=>setPicker('product')} onClear={()=>update({product_asset_id:'',product_name:'',product_description:'',product_url:'',composition_asset_id:''})}/><button className="marketing-generate" disabled={!session.ready||busy||!model||!!providerIssue} onClick={()=>void generate()}><strong>{busy?'PREPARING…':needsComposition?'COMPOSE IMAGE':'GENERATE'}</strong><span>{model?.name||'Loading…'}</span></button></div></section>
      <div className="marketing-composer-details">{state.template&&<button onClick={()=>update({template:'',template_asset_id:'',composition_asset_id:''})}>Direction: {state.template}<Icon name="close" size={12}/></button>}{state.extra_asset_id&&<button onClick={()=>update({extra_asset_id:'',composition_asset_id:''})}>Extra reference<Icon name="close" size={12}/></button>}{state.composition_asset_id&&<button onClick={()=>update({composition_asset_id:''})}><Icon name="check" size={13}/>Composition ready · Reset</button>}{state.ad_asset_id&&<button onClick={()=>setPanel('ad')}>Ad reference · {ad?.name}<Icon name="video" size={12}/></button>}{needsComposition&&<p>Compose the references first. Review the image, then use it to generate your video.</p>}{!generatingImage&&model&&<small>{videoFrames} frames · {(videoFrames/Number(model.default_fps||24)).toFixed(2)}s actual</small>}<button onClick={onSettings}>{provider==='local'?'Local ComfyUI':provider==='comfy-cloud'?'Comfy Cloud':'Saved connection unavailable'}</button><button onClick={()=>setVoiceover(!voiceover)}>Voiceover</button><button disabled={busy} onClick={()=>finishingVideo?void openFinishing(finishingVideo):setPicker('finish')}>Finish video · audio and captions</button><button disabled={busy} onClick={()=>setPicker('finish')}>Choose video to finish</button>{product&&<button disabled={busy||!!providerIssue} onClick={()=>void generate('remove-background')}>Remove product background</button>}</div>
      {voiceover&&<section className="marketing-voiceover"><label className="ea-field">Voiceover script<textarea value={state.narration} maxLength={speechLimit} placeholder="Write a short narration for your product…" onChange={event=>update({narration:event.target.value})}/></label><select aria-label="Voiceover model" value={speechModelId} onChange={event=>{const next=speechModels.find(item=>item.id===event.target.value);const voices=(next?.voices as {id:string;name:string}[]|undefined)||[];update({speech_model_id:event.target.value,voice:voices.some(item=>item.id===state.voice)?state.voice:voices[0]?.id||''});}}>{!speechModel&&<option value={speechModelId} disabled>{speechModelId} · unavailable</option>}{speechModels.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select><select aria-label="Voiceover voice" value={speechVoice} disabled={!speechModel} onChange={event=>update({voice:event.target.value,speech_model_id:speechModelId})}>{!speechVoice&&<option value="" disabled>Choose a voice</option>}{speechVoices.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select><button className="ea-lime" disabled={busy||!state.narration.trim()||!!speechIssue} onClick={()=>void generate('generate-speech')}>Generate voiceover</button><small>{speechIssue||`Creates a separate WAV recording using a built-in voice. No voice cloning. Up to ${speechLimit} script characters.`}</small></section>}
      {failure&&<p className="ea-error marketing-error" role="alert">{failure}</p>}
      {providerIssue&&<p className="ea-muted" role="status">{providerIssue}</p>}
      <section className="marketing-templates"><div className="marketing-section-title"><h2>EXPLORE TEMPLATES</h2><span>{session.saving?'Saving…':session.document?'Project saved':''}</span></div><div className="marketing-template-filters"><nav aria-label="Template category">{categories.map(value=><button key={value} className={category===value?'active':''} onClick={()=>setCategory(value)}>{value}</button>)}</nav><div>{['All','Images','Videos'].map(value=><button key={value} className={kind===value?'active':''} onClick={()=>setKind(value)}>{value}</button>)}</div></div><div className="marketing-template-grid">{templates.map((item,index)=><button key={item.id||index} onClick={()=>setPreview(item)}><ReferenceMedia item={item}/><span>{item.category||'Product shot'}<strong>{item.title}</strong></span></button>)}</div>{!templates.length&&<p className="ea-muted">No captured examples in this filter. Choose All or create your own scene.</p>}<p className="ea-reference-credit">Higgsfield reference examples. A selected template guides your own composition; it is not a generated result from this workspace.</p></section></>:<section className="marketing-projects"><h1>{view==='Favorites'?'MY FAVORITES':'MY PROJECTS'}</h1><WorkspaceHistory jobs={view==='Favorites'?session.jobs.filter(job=>job.favorite):session.jobs} total={session.jobTotal} onSelect={setSelected} onMore={session.loadMoreJobs}/>{view==='Projects'&&<div className="ea-document-list"><h2>Saved drafts</h2>{session.documents.map(document=><button key={document.id} onClick={()=>{void session.openDocument(document);setView('Home');}}>{document.title}<span>Revision {document.revision}</span></button>)}</div>}</section>}
    </section>
    {picker&&<AssetPicker variant="marketing" initialTab={picker==='product'?'Products':'Uploads'} productIds={session.documents.map(document=>(document.state as Partial<MarketingState>).product_asset_id||'').concat(state.product_asset_id)} onProductLink={()=>{setPicker(null);setPanel('link');}} jobs={session.jobs} title={picker==='finish'?'Choose the completed video to finish':picker==='ad'?'Choose an ad reference video':picker==='avatar'?'Choose an avatar reference':picker==='extra'?'Add a visual reference':'Choose your product image'} kind={picker==='ad'||picker==='finish'?'video':'image'} assets={assets.assets} onAdded={assets.add} onClose={()=>setPicker(null)} onSelect={selectAsset}/>}
    {preview&&<ReferenceDialog item={preview} onClose={()=>setPreview(null)} busy={busy} label="Use as visual direction" onUse={()=>void useTemplate(preview)}/>}
    {selected&&<ResultDialog job={session.jobs.find(item=>item.id===selected.id)||selected} onClose={()=>setSelected(null)} onRefresh={()=>void session.refreshJobs()} onReuse={()=>void reuseProject(selected)} reuseLabel="Reuse project" reuseDescription={projectReuseDescription} useKind={selected.outputs.find(item=>item.role==='result')?.kind||'image'} useLabel={selected.outputs.some(item=>item.kind==='video'&&item.role==='result')?'Add audio and captions':selected.outputs.some(item=>item.kind==='audio'&&item.role==='result')?'Use as voiceover':'Animate this composition'} onUse={asset=>void useResult(asset)}/>}
    {panel==='styles'&&<WorkspaceDialog title="Choose style" className="marketing-style-dialog" onClose={()=>setPanel(null)}><div className="marketing-style-layout"><aside><small>Image</small>{['Product shot','Ads','Marketplace'].map(value=><button className={styleCategory===value?'active':''} key={value} onClick={()=>setStyleCategory(value)}><Icon name={value==='Ads'?'monitor':value==='Marketplace'?'grid':'image'} size={16}/>{value}</button>)}<small>Video</small>{videoCategories.map(value=><button className={styleCategory===value?'active':''} key={value} onClick={()=>setStyleCategory(value)}><Icon name={value==='Motion'?'film':'video'} size={16}/>{value}</button>)}</aside><section><header><h3>{styleCategory}</h3><label><Icon name="search" size={16}/><input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search" aria-label="Search styles"/></label></header><div className="marketing-style-grid">{styleItems.map(item=><button disabled={busy} className={state.framing===item.title&&state.style_category===item.category?'selected':''} key={item.id} onClick={()=>void chooseStyle(item)}><ReferenceMedia item={item}/><strong>{item.title}</strong></button>)}</div>{failure&&<p className="ea-error" role="alert">{failure}</p>}</section></div></WorkspaceDialog>}
    {panel==='ad'&&<WorkspaceDialog title="Ad Reference" className="marketing-ad-dialog" onClose={()=>setPanel(null)}><div className="marketing-ad-layout"><section><Icon name="film" size={42}/><h2>GET INSPIRATION FROM VIRAL ADS</h2><p>Use an ad's visual movement and scene as a starting point for your product.</p><div className="marketing-ad-inputs"><label>Reference Ad Video</label><SourceSlot title="Upload your video" detail="Choose from uploads or generations" asset={ad} onChoose={()=>setPicker('ad')} onClear={()=>update({ad_asset_id:'',ad_trim:0})}/><SourceSlot compact title="Product" asset={product} onChoose={()=>setPicker('product')}/><SourceSlot compact title="Avatar" asset={avatar} onChoose={()=>setPicker('avatar')}/></div>{ad&&<div className="ea-field-pair"><label className="ea-field">Start at<input type="number" min="0" max={ad.duration||0} step=".1" value={state.ad_trim||0} onChange={event=>update({ad_trim:Number(event.target.value)})}/></label><label className="ea-field">Duration<select value={state.duration} onChange={event=>update({duration:Number(event.target.value)})}>{[2,3,5,8,10].map(value=><option key={value} value={value}>{value}s</option>)}</select></label></div>}<button className="marketing-ad-continue" disabled={!ad} onClick={()=>{update({mode:'video',prompt:state.prompt||'Reinterpret the source ad using the supplied product and character appearance. Preserve its overall composition and coherent visual movement.'});setPanel(null);}}>CONTINUE</button></section><ReferenceMedia item={library.banner?.[0]}/></div></WorkspaceDialog>}
    {panel==='link'&&<WorkspaceDialog title="ADD YOUR PRODUCT" className="marketing-link-dialog" onClose={()=>setPanel(null)}><p>Add a link or upload images to use your product across generations.</p><form onSubmit={event=>{event.preventDefault();void importProduct();}}><label><Icon name="external" size={16}/><input value={link} onChange={event=>setLink(event.target.value)} placeholder="www.yourproduct.com" aria-label="Product page URL"/></label>{link.trim()&&<button disabled={busy} type="submit">{busy?'Importing…':'Import product'}</button>}<span>or</span><button type="button" disabled={busy} onClick={()=>productFile.current?.click()}>Create manually</button><input hidden type="file" accept="image/*" ref={productFile} onChange={event=>void manualProduct(event.target.files?.[0])}/></form>{failure&&<p className="ea-error" role="alert">{failure}</p>}{importWarnings.map(warning=><p className="ea-muted" key={warning}>{warning}</p>)}<div className="marketing-product-preview">{product?<><img src={mediaUrl(product)} alt={state.product_name||product.name}/><section><label className="ea-field">Product name<input value={state.product_name||product.name} onChange={event=>update({product_name:event.target.value})}/></label><label className="ea-field">Description<textarea value={state.product_description||''} onChange={event=>update({product_description:event.target.value})}/></label>{state.product_url&&<a href={state.product_url} target="_blank" rel="noreferrer">Source product page</a>}<button className="ea-lime" onClick={()=>setPanel(null)}>Use product</button></section></>:<div><strong>No product added yet</strong><p>Paste a link or upload images to get started</p></div>}</div></WorkspaceDialog>}
    {finishing&&session.document&&finishingVideo&&<SequencePlanner appId="marketing-ads" document={session.document}
      initialPrompt={state.prompt} targetDuration={finishingVideo.duration||1} episodeCount={1} catalog={catalog} settings={settings}
      initialExistingVideo={finishingVideo} initialAudioAssetId={state.finishing_audio_asset_id}
      onPrepareDocument={async ids=>{const doc=await session.updateAndSave({attachment_asset_ids:[...new Set([...(state.attachment_asset_ids||[]),...ids])]});if(!doc)throw new Error('Save the assembly inputs first.');return doc;}}
      onClose={()=>setFinishing(false)} onCreated={()=>void session.refreshJobs()}/>}
    {menu&&<AnchoredPopover anchor={menu.anchor} onClose={()=>setMenu(null)} placement="bottom-start" label={menu.name} width={160} className="ea-model-menu"><h3>{menu.name}</h3>{(menu.name==='Aspect ratio'?['3:4','9:16','1:1','16:9']:['2','3','5','8','10']).map(value=><button key={value} onClick={()=>{update(menu.name==='Aspect ratio'?{aspect_ratio:value}:{duration:Number(value)});setMenu(null);}}>{value}{menu.name==='Duration'?'s':''}{(menu.name==='Aspect ratio'?state.aspect_ratio===value:state.duration===Number(value))&&<Icon name="check" size={14}/>}</button>)}</AnchoredPopover>}
  </main>;
}
