from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
from dehps.config import ROOT_DIR
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    predictive_route_reconciliation as governance_reference,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    branch_decision as marginal,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    joint_residual_increment as joint,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    routing,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    temporal_marginal_increment as temporal,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    AdditiveManifestMigrationError,
    verify_failed_replay_recovery_event_metadata,
)
from dehps.research_os.information_theory.progress import (
    M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY,
    M4_V2_SUCCESSOR_REPLAY_FACTS,
    M4_V2_SUCCESSOR_TASKS,
    P2R_TASK_KEY,
    PREDICTIVE_P3_PASS_TO_P4_FACT,
    PREDICTIVE_P3_TASK_KEY,
    PREDICTIVE_P4_TASK_KEY,
    PREDICTIVE_P5_TASK_KEY,
    validate_m4_v2_successor_structure,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    M4_V2_ARTIFACT_TYPE_REGISTRY,
    M4_V2_BRANCH_IDS,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    M4_V2_NESTED_SCHEMA_REGISTRY,
    ControlPlaneManifest,
    M4V2BranchDecisionArtifact,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    TaskStatus,
    governance_execution_metadata_digest,
    governance_request_identity_digest,
    governance_reviewer_decision_digest,
    jsonable,
    m4_v2_canonical_json,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
)
from dehps.research_os.repository import PostgresResearchOSRepository

from scripts import build_m4_v2_global_routing_manifest as global_builder
from scripts import build_m4_v2_joint_residual_increment_manifest as joint_builder
from scripts import build_m4_v2_temporal_marginal_increment_manifest as temporal_builder
from scripts import build_m4_v2_three_branch_decision_manifest as marginal_builder

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GIT_COMMIT = "a" * 40
RECOVERY_INPUT_MANIFEST_DIGEST = (
    "1331950e7f2c74ee8db22bb3383d1defb241b4bee0253d2fedbb8cde065cb470"
)
RECOVERY_INPUT_SNAPSHOT_DIGEST = (
    "d76b4200d439309c5a0b9c9ac1bb42b22649d3be182e996873ad8825fbaecd50"
)
RECOVERY_INPUT_CANONICAL_SHA256 = "338498fa2134a4c4c6ae59f7e04e2e2cee21f26b4e905325a70b1f59c6972782"
RECOVERY_INPUT_COMPRESSED_SHA256 = "55ea725ce9f43373d95806c0ca834d5a9fa2e9ba2481c9d7ed99ba6dbad16b88"
RECOVERY_INPUT_FIXTURE_B85_SHA256 = "657539110a3a986fe7d77289e4ed66b042a62e1684aa00b30b4f709e92eddbee"
RECOVERY_INPUT_FIXTURE_B85 = (
    "c-"
    "ri}X>%J%wk7yiVEQy;BjotL;L8|OVr8;R+oPzgu5K%X`6}@xMX(7{S^1vTf1h(B0)YSskRS;vRaLTFL=l1T?JnnBzkdC{pVg4A=F"
    "cYo{VZHwopyiu-_Ppo^0#oA$MbS^byhx?^Q(zq!Z4>Mr7Fj*cQU0Um=D3(S{Vym#KMZNEM#G1U@W`Hn9I(}Y^)I3%38e?&z?U!D<"
    "4Dpef&9`o}ZnbmvKEk4`<^T=7s)>2R^HD3g@%)(}drbzn64<HM<;#tE)1<3RkDI^9kpwYME_xifNh9i>#$e+DKmvmsZG}v^Jbsqn"
    "RtFDr2Pb+Nc_Q)uwGEmvlPE>&6$ev(xnZ#0gbB&pI<MQYhIc8-"
    "$hkzpT;MRCzQBKboK_Q$|~6mEy@JVK5~uw{QJi!u<NOnYD46onKvIR>xliTAQDKJRe_{i?i_i<d?(aqdy%TzTD+IlRq85{a=S~Zh"
    "y3WFDCQvSNM41Mb0@^sRf45OVr+5E_vdHN1jr2NnwRDme8u~4bP@>pM;3g8_8I?wXsQHK^mL9&(<iDLdJVV#DtZ|Fn?A;NK&SWG1"
    "|n+L{u!`Y0n*FUdQ(B7h=rE^WV>}K9#G}G|u4)GH^A~QY%cittMIFy-"
    "BrllTFig1}ReBqo36a?R?BiMu+9bQZw#L%+73l`Q`OFB<}pQLWU+zdFh=^3Cl<S7Kv5WNteKti-lJu0?)o^YnV5TB_)-"
    "?x+{@l4b0u$LUk&M9Hch7+L8mrL|P{_w+Vl6OoOi4mf)(4H8W<k4_+qem=h+*)VCn823MDO{jcTnyqqmtz`Xj*f)SX3%#CFR{S`t"
    "aiwTy{PoFerCPpb~-XhPXTAiwZ3_BA<-+~<f7S4VhFLeG>Ks)pKvLS9E|5<w;t=2XuAvv@Hs|x+Lm1WG8hX^SF^-"
    ")+KEv>0u)#91T(4)Q~((1F*c-"
    "g4%+H^_AohkToC<QOJn71r+QibJWT=rTAW{b0#JG?qWIb*>}<*EYuV+U=Vp8sb_R|UokngjchW}h$4N@F#oa9Hjdc!(v|Qk=`m<Q"
    "P*i+2;~1q>fkZq=LE!mdMDVVN9G9SW4NqqM>c`fcKuBf4s3U5d5Mn6i;QFO-`Z4U{t`{VI{M0P!w1u<+HA&b1uO`ItK-TZDE!#b;"
    "Cfs>gDXe%K3OcyS_}NSMCa3hH`jcc+t9OhkueSKBUU5WEFy;Ima+DrL^YJM~Ip(DdrL|rj;f>hs%$x1wK8`G@yl|PjXT^am56QB+"
    "GcQw7fzUgiDa$z_p7O19UKjzDlVi#wQ#L0?MVFU2SGyO1?l2aw`V?v;|cZ469T@MNz7+MVpeDgk9Ax1s#-"
    "*5zd7hrz5OOgb%6~mN&`}v1lueU54K}$I*z|CX?GdDI4)XPvYs>>D87;F3RQUER%+pdb+fOlYovvPGZWQ!FJeEAVAKGkQ}+j=ork"
    "34Vo3hWW*qtlGJ&YAQ#p9l}6^*Xl7oT1z1~cEvv_**zAQ@D%Xr@G8s}Ip)@fk6ESNw86Ts!Hd_%O&%8o!3!0Kcfx2rEU^zmuridb"
    "(77}eTn0XN)q8L>y$-"
    "w>!#chrP)1Ngrq~{El2Vzo}i(prp`WUXt)>ZKMpONE_v$I@it!lX}=c#Oc5QgLG^m7@9>x|V1m#0^sJ~sv!^R@L$-"
    "IT7Zc0a+qU`9Q>y@rWPCBsBoRe3UwMF|g+JkvVCqS~y5g<eDAYbwxVD}iq6pt04?VZi4ThwovgYECfo3AO;vK<ON_Hl&LNc3i`@a"
    "VISF)+mWd4?$rWG07>5+usgXULXrqngAP&ere@kTJW-Dl!hEQErs?aln8rZ17RY#XSkul4AbWJw_}VI?ll$x3jz_)JQjo5fJ7@FR"
    "p40p#9;8?d!6^XaDh?4Hyc<eHL(5ZY(~;BdGYr3yH|%Nhtt0to%}pKK74m@bUc0g;RL@w>>oabAOMY?hHjk}IBoL!@ZkN2<HOg7Z"
    "%(E!-o80GK6r7mc**hMe|$JP9<2QOTP`44XQv-OT@8F_Br&%NRup~#{#V29!~_clOAJ32g(%#Vm{dv*y2c`qq%Z(eu&zK2%eKxhu"
    "CFExzh({4f`hD~dIyJ<VUm+E4!Q_<0^iSy@=n8EYG5K&VIri@aImKIuN&%4KlpB(!#Q~W*Y_ufuQz@T+7?bP2SY82d-"
    "P6ANLVo%B4HiGjByBN&QJkZQXpDLO4YiuV(}DQZPXAMsrAN206SMT>azTwYidmixNIk(Nm9zf;ne{CYAyn@2kmmUh+Ik%60iq=0x"
    "%S)QFs6rV3|~w@TVKb?D`4~m4z5}>O6sw!&)Q&TPRcl7|j3$B-"
    "sFVRwQ9DN)MYUs!dvYi7_R`Vc{Gz2G(?~8GwdOfOm56%fZpBgCAclC6stb8GpgT#4{M`63C7WAV9E0IWo|a4d@)8t0O0Ap)~LUOn"
    "6oe5RJ^}EzlS%l8{MZf<b;9U$)bE1@w&YQn*Z?PQR2%rs?&-"
    "$5NPr(ZNmu4#Vtg!2oMLkrK>83@{EtRN)Jtm`W9<s48HR#rp@=bbdC2ot}LGm<h1HOM}_XL17RE7()q`U}W?q>);{>P=~Ytsw-"
    "$vA&>w{#u>Pwi5R7c7H%9Jv)h`yEN7VVG6whixXlY+j<06p3j<ZSDCf{>kjIX(9Us0wJUD*w^Yq}=tG9nSd^vr0{Py+RlcTq9ra!"
    ")V`{K|2J0z(;eE1cnZ+r=HDoe$BdGON~BeLOJmjzRj(9hO$c7h1SuK*}u!El}l;E2I`YZyVpQmHjoA+*il*MU~6z?D`a8On!hj45"
    "H)_Imr-e*r-B`s`{P0Yw3MuP(0>L=j*P$fwcB_Jfb*ya0C-"
    "i^kuEc>n%y?09T9^5V5hFr&i56*?FhAn8!N@_<7uILEjFzK#a;hC^60SQNA#B!!qA@Y6k;y?=Mh7jguh?>{{&my4c*SVUL_1!Iw="
    "1fJ9xtd+TF7@2Ja5Tp#uNifh){FG{u@O1)g6a+5XhxgzCgXpnr*LjCd$OtQ@fJqn-"
    "7=y`1mto=oy`_ub@MIu(NfItPL<z|Rk(C$^SJmv?G6eFnd_2V`D*|st)l7<{pz#tW)>MYqT95#VsY7pkN>v6I6i6>jhb#piQx+f("
    "SpVoA+Wz{~t$nI$t(qqdK_rZf>48Kla6LG124rk}a-"
    "c*|Q>i#`btnmV$tbeEnPtEEt)?)UvIF9^4iqE@1E`ZAy&{u*1JQ%L6oUBP69flv2pJ4dQOGD1zWJ@e;YF|v3bt9|PcB2UB#Q9USX"
    "9Xz_W+~`Kwp7s3p8GMjM*tHENn^pR=8j=>httz8O`c|_UnV=pN`%fyqdm0IXF3bv1V15-|J8?sAehub<^-"
    "m&jC|SU`lf*ov*O(&~H#$&{;+F)>9lQNdO4+o(Dh&xIAS%yb@dZnq_nAuxz#Yl~C9AFD<d$h6vd%U+WcW0?#r1@%Z4)i=PkQPv0H"
    "9fB%q|9RAP47avY;&h3V0Z%nYw0f;(tP$;;5S(J*YY8zDnRENvp;JqR<q2bvTI0@m2ppyer1|Uy-dz<SmnF_AV3sx$_Q~8jTA-Ec"
    "_#15;hyZ}K-fKxge3h#mH!=!{Di?1Tc<x+k;n?>j-d8n0u!D}_$2+@BL>kIS=dN8|e0=#SDd)rIaMf&9M_%;2#f9-"
    "$HP8;kyKh4*8_33%K5xkW5=;fWSyT`lwFv}2PLbJ-nRRg&C@&EYt!<&~kzt)7l({dmy>N?30u8ZJC(V>I@B!+c_Wr8zHDO)J7VL>"
    "SH+Tf+iwHiq{)MOXo><Zu7-"
    "bU*%0eFS?5#B)KA&M~Z5#YX<1ZLx^SMUplTcVrH3kfiq;p`O$B=lgDi%8mr=025hb~UhNi{VuVzG58+W=I8w1-"
    "RZ=_+y@9a2`wpHqy%sNj0FLkndo@;}Zj<mNmJ%+Z$pUVFV}MR|A~BbFMN|9ARoSg=rN9!%c9tr83YuOt%wC!&<`vf*0F-"
    "S8F%CxvmiqDMY3v9Ha{gOKCwJqLr0`JWd-9v#*&3u}BruDuWDQ3*c-"
    "(Q)+vIOEp^^V#v%2@G`~|=v@Y!36=Ibm{uX<FD^;IodD(<q$!1XqKGkuA{4yfZ40<;ae;d#M{l4PFJ66kfAq`YPG4M~pPZRg#bem"
    "og$iT?R82DFJXTudDja4$Q#i&dm@lwB2b1cO0Zp-d5kk4W(I!T<Xb*tNR-ZK|gp)w!GgxIP%mG4W4!esUa0hLI#sTmOmLd=$#3Je"
    "pjoYQY)~&#wggm=w2KyMJvdjC4N`T+}KK{bjVASnzT8&0*a<@BvdFd}7+I+J}TVV9=Z&^oTyN_lI8m8Sr3yCuc1i9LnR3*9%0Gu^"
    "!qcJ`MbHglWutN?+2Ul;U6Ox4hJF?wiY}|j_jFfKs>g^cowr{T4<1Pqwzpw5hF&n;k4{6yD__}|y-"
    "4`D*;?*}iuK)Lx(G73dynVd$ch~1(1sdP$6_1+;Jax~xSdoA}R48fl0#LTlPND`32II@Z0oQ_<3Qc?XE}P6u<uyoWfyF6I0a^>QF"
    "6&*bZ2>NVwl%qf-"
    "z4yD0mQ5U7IL|&%8QZkG@JoK(GHe&4tU(L?6Nf`Xa**|W3x9A1rNqr3h07@f;GZ{$>bvkc*xQ@VS~1y9Qe85x3nKFVW6@t$pu!cx"
    "U1c5VF9NI2WEp&d#^Ml1b_-kFqr@h6&0WZIC^40W<XVxdysf6TIw8N5bqrBGL53gy~a_bml+21La7Z3%mz$c7X{x<0UlX_)Bqf<("
    "3O%qD&|3P$U@b=?9kwrl{K`5BUCX!B{hJL8<4aL|IcCtcvG1hQvj@L6pFBuas{N0QCa{8dN8}Ud}DC|f<?3@av+}w*c*&DQi35GW"
    "$-"
    "^=9ARMQFwcTE2^G^E954Fpe28V2L2p@KN>^}2X+nm<H3&I}7!+WZO(iuMB^2sO$$PCikUkHXeH)ZgT8kykxGJA7W)$b?yYN`9w#y"
    "rLd)*>0X=%4MZ_}=BeJrWmL=}iO@VPHSW>tU(OjbUE!x*0=sF4F$1d#{L2A6@VN&yQ2{0$oc+HWQqh`%O~nMhkwS=XXDI7S4_1iG"
    "wBrVL!lLM?)JGNNaA609UtYoK&y(j`5VeA{@oY`iW|g2Nhu{ELt>?54qT16e0P;GjJQ5Gu$Q#iWwpDWIPqDN=zR2qvhrc_Km;0+t"
    "M8l+b-"
    "s6O64W#egvhfOLG#Q({)g5(vo)*eEU;^r;FdeT?@S#bQ%o7U$*iODnW%d&A&^jwg<eGw)2LL^jDl95sanp_{=mPm}?WOc=0>MB6l"
    "2MB>Q`KTcfsvPc8u&!F_u<l><CAi|Vs1-"
    "2FhR8f0Ebq<Q}K%opp0jb@>t9j6Xw(gQJ$dRWoChfKctWe6do9AIo83<)a)@7^)$JD}HXz!U(R(UQfdMk{cghHu#F)#(=$tZ9uWp"
    "Y*d4BL#gC<02($h=ZZ3RB^2wv`7PRfI_FHk@#MHT&FHmj=Ak{sYX+?DA>?nF+SSJq2&7$~u&U-"
    "sng>u$WIp{tHG+NyvldmT{wC@GMtkTEO}ynH34Yj>QrcgMpLH4r^<&fX$6TdQUrz4ED!pbf0{$b&y8}YYqRNcN;(rXPEhm+5EKGm"
    "Z1S$%zi7Ev_kWV1DtS>ke~uf(pIZs{*2X_MoT`91shnz)QPAB1JK~Khmex>5;{`U#NvN~6>kd0Ri(DUYTy7c1bA*Od|;U?m{~!59"
    "Sf2oE6^pTq6Xh!I}YMTR@5>RYhqY{Dp%tI2j7L38_G~?Qhp+b`vCFf4mKRr7cdF4moV{MHql@ioSaw-`C@Q`uw>dgP-RzL5Gni0n"
    "V?^Rpfd+`sWCemK8IIK4o=Kd*kQLJ46)(XnCzr5xb+GL>nWQ<Bq=O&zEIwvt1zV&=)f1)W99{mUSO3R29yBtDv*zwaA7@G#szX+K"
    "rWFCs;WLGN+oqZQOt)YuSC%zSlD8Cey0*`9~sVeRPx34{9sJ;-"
    "{<gQw5Khx>Lef40;zJyE@T2OmD1i!5Q1x<hzjTkHPI4i5yOp63#F@YdIIb!&}B=32uwF5MsQEwA2M2?`G8`g;1B0vri+f5K~%9A6"
    "bypLak~y+kpMSA?^KPj@(f@E@Bq4}igcJeijyS)G~!@e80mH_Hp83QT3|Do5aiq@=q>Pr(#2URh4hqPBqGyEVkMyl@M%uLRskT24"
    "3G*-ttr<SQ$r%Rqaj*mYHrSgniMIZq%feAIV127-i<-QumD&wSbIxZXP(d`<hoQ-B-{l|2|h0vC+rbs+6ow9=0wK2MR>T3$0-"
    "O(2?+p-"
    "iZh_4((Ijk3y*3bITD@`^Re4FR<boOE@!bUayBO{0LVuPCIesyFJ(D!fngDbgNbZu2SMoIl1bWw0FX+<GSvj=!ax`>0?0J1nBm;U"
    "DoN6zw-GjtE3hN&0v00@dD1{3fpRE-O_-"
    "sy7N2F>X#{s~azkZpk_LD{lOjYy1xX2jBMi>^oRbiQND9C_pn{I%C934MW+EAEf*+&^0zIl;2$eEyZ-SM=v`c1Tr&P?zgN{T7@i!"
    "tx4$KVIhKzaemEDH%=&g4kB?v$Sj%E<40`tQag?E8E5*Q0S6{qe19$ENef&T$MI*3&Thk#R<K=Ts}LvWB*2vSMhK;o=oB>`4eohZ"
    "8%lSGNp2Cso9jf#O2(xe*h_cP9$``e7N%8e!+Fz8FlA%OWn3PCst0m5Wz;VjrGYuq$goGnqn>r2>NB__@>I0yv*$w3{R0+WE9lNc"
    "Vy+7r_;Jb`+^S9#j~RuU#zTUa@vE%54o2DTn|sPI=(0+`ec*g`ossTSw(V~&B+xlJL`BSE+r{19L+ATh*EQ$is?@k9aGC9ncm$PB"
    "Crt_m0(=u86qC)_5fX!Zuq2>uqVt%5BU@Kq}*{jlt^UOR8J0%!RGCsWAV=>o1?;S+6zD!_wSMYD{qNEls!4+a5L<n8fWtQOOHqLT"
    "+{u_R6vmaICw0mCQ^riW2F2<`ZTa^{c%*bGbz?70X0Hlie7#iIsuV*}U#9YJY;{GtZl%Yg4dB$<-iz_j2l;iD-"
    "@mcb9%ghc_?ED$%CHcff{lY|utR$B0!Xh<Fvpc*+J9V)B?EDY0FFV1;}ghG6k1RemY08Dk#nmr9?`31;+d)9$+c;V6w(4fY$co#H"
    "d#7O|w9Dp$fUX=#;0MO;YB2ELK!3rAVYAP@<hFFWUU|Uu>j2D^(tYhe422+lVUxjP-"
    "5U?OCj09{DXc6CSL=WDAs9r@ldnq(^kD@5hB@kg4ya0GsfYq=-"
    "pf!xZ7Nrux)B$T(%^8N6CW>WB=cw?v3F|H3_aJ=`NelDG2_tY2X$fNos6#l!Q1TjOd@2jcXOAA=hK&)e!S{6n69oDP&#(|d$7zdF"
    "K(|@o(0>nL6liI{M?91Y#Etd^Bo>ci2LL`b^Bf{&9D#PnNQV}Dp?rH2u<{P_j8{hvYUHwmbtsfk=s>A!-"
    "RqzR!U!B$N(KmHQF*it50wGlV~U`L5~N4aK?*=P2d@lXhksy-"
    "!Hhu$KsqNFOoZ`=m&OP~1Z@Uz1B?anag?%1hK14?DOl%1R8q1g1)DSx1~lw-"
    "T&vqifipV!B%#{T2yn<~icOU96&yG;ta=VWXjm=*%K~{7OaltS4hC65&6BEiF5ucsN0=EaU8Id_4#<j6i;{FyLl7@aFie;;_(Bh}"
    "#K`2^9L!$Fw(hjxI0EG@K`Cqk&VYZ31vnq70sC(w1T7`-ZwWKNj7k~{!=WLR!3DDBCYnNeFn!?I5^NOEQbXxPfZ-"
    "?m#0a6eLV+!Sc}7WqcsE>sQM_a*+`~q9+s;?cpg2&mNT>C%Y(j!cMhC}&j-"
    "^UwQez!4M%o+ZK>%X|48eXV1BL;HL%FGd#0I#SXO=a^J+dN90v`bfqJoG;mZ-"
    "u0XyX^2Sw;g^6BT%XfBcZvoH3yv%S`ojJOn7v<FDRF20(xo3nc=83Razsfo3HIvjT~Pe1W6qs`A9c9XR|4jxAs(I26el?O_=U1xN"
    "5qi3yVg5mw~-"
    "0PcMNHpF<9D%w1LMC<!Sm7+}?f*&a#kH)1efp`WMB5fpco(+HzgLuJGhZ3?O8tOgJ901Y8V5${tXQX3Ik%A*YQ?e)+j1Wn`q^n*+"
    "N#W)o$RO&TQ(Q_U*bxx6Jr1cc?NLy`jG|+#L=L~tDaH@wR?$#425bO8IEjY`vH;cPS#hayf-"
    "$fzsR@&mT?PLPlS1bRT>!<Qh&rIYv=uJU2rzr1YN@~wdBFfZ6qd=<3Q^tLfR<mu>VT+20=xx~0NDVI*F?s(%!Na2Y!pxspa~FnW`"
    "lx_PfXB(4@rsklSCm=o8gd~O{@Yy0aDl`{+9^bK%3yk!bj1*jG$AGMSwfnN-!$~{`fJi?)L&4WnWYQ?(-"
    "4K?Vz)P=Tf8s)n+cZT;ajsfB<;F?_;KPRk&z6<4_quDKL=+mV`K>>nSh}iW_V8;FfSou;lPr9M}+Us=y0U233Y-"
    "RE>{jX>S8s*C!d#7<wW>Fkk~fu%Ib0b5QUEKJF=l*#W>s$eV;DX5!Bvyn&3c43M5c$xx6*#wr~>gjjJpw&NVg3oKm7A`s$-"
    "{=pen3SUHUO31FVKrnXSBU^qm3(|D71tSH7tysXUCTHNOGPEBAf&mkTqN4YXL*oUV?4ZCBH?T2vQi19dLGj4BH(JI9+B3#!rv(cN"
    "0pN7}MhOmFVTrv-"
    "I669Q1^M48Z1J#N`xGG@0Jz=*)M#=j3Yw;}rLaXMj>{>Ju7Lezf&(6Xw>)!8N328<6M*7G=*Yu6F*?T$hQ@&e9hMHu0_Fkfj9ys7"
    "gT`QCks_GC$_iX1#r-YXGMgY5%o$vw%;-"
    "p=cs3n%g>(XIGhqWo?#ZGVh*qEzz%b7?(=Le#poMw@>t{3A2z)ibI&ms^0a$T`mwGxCXF=twsI-fzKvUqYrO_0BtHx)s*D<YY8PI"
    "lZ0!FgdLOUy30M8{2cufWaU;yK;!0qG=SPg(k03w(GFb)axHj%UsXj6o%!$JfBBu_hEiGg1U?sQI!b|Ex8AUrbn6(-"
    "o)oG4(PC0?-"
    "q!7aZ`8Gc}j)Le%B1@@$)S9DYq!U(#I<;rkf(r17RM}!lff#wSjrddF_Xm14!Mw#efKp7w{CWH3JXmbeg7QPt{n9?tmA(iA-"
    "&>p`78Vhh|WuK#4*EP%~9a~KpUsMdTPeF0O>;hQPBt3vtV)0n!JXAW!=;?qz451Y8M374lZxNiM91uE>4-"
    "^HR^K?#98FKpx)R~*A9R+QQ=hi_H>1davtOB+xD%=EYS8GFLxEp{7G)wzFntT+r!2(HX9W}5K;J76W3-"
    "$}OvCX_wNryyxwAM`+ohbw@vlLv0nk9G%N4t9*2B~mBd&+8z1*Dr>*nSx@6>e}qWg&ROA3c%@5GLp;gPKIJ4)Vw_x3mx8L<J*Ku*"
    "9%e7>DtovJyT@g8*6>emJP0)x^`&8l8pBSA>L3B#ViMD+SN#%xRA3Jd8VVKX9@SoUn<aK&kON4q?j?_(_Gmk}AR}fr<)DZnB&;+e"
    "g4{ib;ZJEJgwJngV=iNuntt0jOSW5p059DN5l5+mBfV=zayptwA#^5p$X1o`Ck0#Q}As%xJtAzqPQagpnTB{q-"
    "Xt5N<S`D23Tev}j@0xCk|YFjY&TgFt8;P7%x}d(rItW%yXocpogAM1XRF*Bp-"
    "1csj8Kh{!8#J;K(*;A;t{SY5*8SgaKW5(T_7ivUbQ=z9%g<Dq>}YD&gJGnBa1Y@~47iG*Av3VYG<I?y%vJeV#hgp~mbL%Z!xNNDL"
    "qQ|MAVm?EG~Zs}MOER`w3SLlaM3CJKr3}F{JZFN$djH^Ux4FC!(>^y|+N8SYtpez81jQklz3KVFNC9X+f1xW{PLtsz}!rcO7Li21"
    "KISOD09VQe^F*zBYZ5BYLwEgF5f=UA|iRi&?OVaq3(3xXZoVAwZ5VVO{-<?6B#fA)~onn;XjM7;0!YV=G=8G(s0d*+CL?}n7nM-"
    "s^0+|7(c}pmg_IcqMIPoN)RoG7szy_!d6a?X-?eU3qutC7CIe>!_E&~a|TwpC6y+|?@scwumys-sAf-hoK!Ix-rKZN}a>V_xLM2r"
    "d0z^(fXGgLA0E=Z#)g}xa@9=(lp8df;4nk*^f08Uk^1kMc*fJL%E;f@N*u;M&iWdMhwBRvW0XfsrWF;}T@MAcT)wg>DA9pHry?Qd"
    "w^7Dtb7uw>CiLADIsx=_-"
    "b$MQt@ibPfkN~R6`1BT`$Kx?KT5fEpkYAB!q;75Uzh=IGwoFuHA76CAvk{$xqhR#Y7S+uY*kl;dRpfM$oWdn$i%HxJM*rX|6!r67"
    "3=d*~tS{MsVAlRtKWK+nS3s^18F%%~$;F<uYZb1z|jRbTAMjej<5;$g(o(SlDld$Kb&;SyUI6BlQIncOPg;UyA0llo2N;5ESO{Me"
    "v5S2g?UiB1XTYej=ED2|+3T+S`>x7A?eIgePF|`;8aYc<`6O@w~AXCE#!~TOAL^08T5lZ@~Jv0yOHHrY3?J4_-"
    "oDpr5GL7$rh_$67J>c?~3OG|!z-{?c4DZIF$jSjZoq)du*|D&jwNlw4I+5Z_rix0G8=I7M00l`$OiIHVsP>G5-"
    "=ypz*o?|`paLndmx@E}zzi9TkpR6{jLxdVvn#3#rn909B2W1o@Eq(Z2Dz?;+FQ$lgX6OBV%hpi0rdbMOEF^D01ewtUVylP(1|&o0"
    "uTaBB7BIW{J?~@GXUmTr&xh^F?@JH$_9ZC_ZnV9)BZ=I*t)bDzzehH$j>OynY|5iu~Ui>7Aj6KK0Ut*zm^G=JOJ*rIY+8G#WbCxV"
    "nEYUFiku6u!=mxCpNZ(N^NjxtxC~@)B<-"
    "+sB(tE*O{WQCv2yN%sTjLco`}WW&<&O)f^|56#L7JI51pAfsuCdej{9DQ}jF8Gf?@{FSE7^%6Yk*fDRQpxn6*(L!pvbaJ=X*@LC0"
    "71)M_TpbNp%aiKuF_=RdrG5B^W1vC*9=~o68mv#=Ic3EIWN&-SA_N8*r!3cog3KI%O$RVI6DXO!;0pIQY26SHjezm&2y}m-"
    "R0IjMf)ltyy3luEdswrOVHRMXd%m8}9m4hh?&t#Q}GBiONU`HL;lB2yGBVqzfu7Th#%N9t}f-"
    "J#h5G03hqcRtfm@mvS##>=HwW#&(i1X@zE-"
    "q)EXRXEPRwP*}Is|(SNK0v$8e9jOB3%S_3YEBxSGfjYAqKpvK}Cfm5GjFZL*f%xpl(=3347rQW+mEO(_l$j0XjkwQx(-"
    "Sa`^BTDi^8}<KVazqt@;>fPvC1Djl{7#FwY@6*CV$2VR=#=pjrS08z@)V&>s@C^iQ>&w$q9s%f8vinf>pbmc%iD%Mg1vjgk{elvI"
    "~ZM|*KZuE3kpVD=?#Ojpjo8oK|9|=0i4p46(yTKK=-"
    "*K(m_mUDFW2D3|ER77Q(uo72t~F5>B$NRz)+IXq4wRIs1e=0Y5ETr?gBO}YmD(t+Gf*-"
    "XmP{*(q`_Kn#Vz<BI3Vq*(zdsvqZN$U4FF~=fGcjVqgyK^0<mXc=@1o5nU96~0F~CE0EasmdMbw*n5R>vf~rC}L*;m^VM^wl@&xi"
    "JVcvuwNn|vB?}7ze2lxfZ@)a0U1eIJ2l*yZ{fE|UX0097waPi>5Ee|(bUr=uD0#b2N3iG5y6k=wyBLJ>#0sIu~1P}zkp{0UIM4@1"
    "cfzT-qj)6m+Y^L)WlA^eU%(^Gk=z*97@G|(JqzpbNpmwo2S}Gar2`A_6VLgfj3@`f|(T!vtP^czt5269Cn0W<y<gf`9^tCwJkTEd"
    "hKoamLV2;E&F<b_=W2C5oL|Ha@JwQ!RMB2~=1}TP4?pxYJNU)1kd{e+RK+E96u<WcUibMI>4;~r~r_Rn!X9J8e@!%Wq@DMM>e4%t"
    "c4}5MZs!u5uJ_pcolZl#}4Adhn<gii-"
    "y8?nlZ)5<9O^HyG1W<xHf~k4<D!?kN62J){N|gYhw2M$doI$b~$8cy*JJ@{;XGtzS%{#E2^`cPat?Yx9IYxqqC33hB!bugQ233~<"
    "{*tGdxOOg65vz%#V=7KL*hM;<Kp7XMSiB3G2?;X=SV(&VnS)D$Ok=?-Rr-"
    "P?6e_>=;L)s^1Zb<K^Y@j351UB!zM5nt%C@G1@RV_C03VV8q@$cANx@@9)l3TpCME)G4TAvEh!hYg0g6Ncj%a`(sLUYX1+X1+l-"
    "CU7A)rZsA!HHoCcQe4-"
    "Ff59YC8{z5iCv(0rt=yp#+H4FlCuUu!7UWb~`{IS9Ehs0!$GI9@GSg9A3?83&UV^Q>^9@t;3xctb5VXXH)1Tlp>Z5AOor`DK1LkB"
    "f;<)^c?6w07L`n!Oupjr24SdA2xMcj$J`79dJsqIsj}zRxIT>m7<!xOAO7&f)Q1C7MQb&A?BC?J{5<O09ik#4-"
    "Xs28s+Ja>j_GcOpbDS162ujl-e#K7vvG4!C-"
    "rolp^3F04S4()HJ0WDAx%j=`nqH*gzI503Fl7ih`oSV4kp}qEc8Dx=ZJ?I1ie3t17z6GsPDH{ws`8bHFo+hqPINlR_vWz@3Dup)f"
    "Vl87dwrj_k<>2Ey0`3bPYh8}LA#qyQ{RA(uPbye*p2>n_$QlNlze87dV?qAdpadgySZqm+{JmOUT|MJIEJ5w=(wcvq0wDj(H}-"
    "Iwf+;7NaSQc(6ZW=nxKRt?q&C|@W)FFJTkEh7jVtU>^e0}iJ=fm|#MsV{*_^*y#9j~&n!`#`5#n00_!+)9=rRS>C;FeFPDp(zAqK"
    "*+#}jLM!495_QMUZ8(L8@-?2Ja%wfY=#S1Ewa-"
    "^*lIo1NOg`uBo*8z9RN!ZH8@6MX^ArbIaOYc!b;jwYR(kzBWSaAaCZj}?)>WdH~Mv@LmI&UEO~&oQbBDZr=s`5&|xz$cx_Wqo=BA"
    "dT23KR(9C&2C(hN)q2Hj<y{#cY1s2xq2OBsScxBk&0>Dy3fH!Uqa|7>F74br6OcdM;fTDtP2Y0-"
    "?rR}q@D>d$Cg|a267BU^pp&WJ(S*NrILbk**98d-Dt%XB`iUYFKc@ppx=@RArKDYx99>Ny2)f_yj(8(#d>jD@D8%jwmfJG(1-"
    "4sUgufPN#jMh{+go^Ph&uCBDXYt5xJa{;(7`H$BPv;mk<u1!gr<}OgsQ`Tdhr)RRof_X{TzLyhMCF2uixw~!W04#%|8c$8X)xPp?"
    "t{Mjkl9@It<Y;Q##&9FqSKY?AV^&ZT2LHKR4UeMF{v(51q!cSPL%`VB`4`fm%FW{O(b#AE@h4<s>0|%=}Od=YC%v{xB_ocOr--V<"
    "O1pZxl55MfAgHlTQ~=oFYnv#PE)gi2KEYXsm_yAv`wQRM6mr(8w>ggx<n-"
    "`NG})%p)Fh!=W`VvFDWn%h3Diwo87Iun^iiqLOX*zTBSsy18RjTM2Zq=C!;wXDM3f9FD$@e(*_LfN73<cij3T<1e?{4DuFgN%Cv-"
    "(fQiE?MowohRptu(9Sk6ZY$=G#GQf9AnX1Se&|wprD)hUO*?wOB_WW76zWOw~JiR(CbYl#Dv2cHMe@q{2{`C9B?CKMQem<F(FHMz"
    "!-01M^`aF-XW*3~To@e~RCzqu?s!Xkvzh6;7;<G7zxxJgFoPUHND3>dR2X{MH7%t$IzLdP}ikS&4u_{=eTxBvgWS?n2(LxIY^9KC"
    "gNfu0qA|#M+kaf+#wZIpZq}WJTHD!2mf3nDJXb<pH)BWVE^nP2Z>tUz2d~<tw<U7B6uQ}WHibtP=+(R2T&mivMr8hPwZ+qoKVg!4"
    "7;U4?Bj(Q*Qs#}TO-ru{IN!@XedfyE^&7^lye4n@7+&08lKVF8<%a{D^AJ3nCoP{&8#sB?mfy<`tB}LOk1$??u>@3W$rcm+EFyGM"
    "1&!_n9GYR(16{Q;*1B4?5i<FD0a`qIn%<x&-"
    "cty~r`F?u?S)QKG=htv8&$?^KRzIeMt7$&{*fjiXA2*aW@1{~eUjQ{Pr?BYL)4XWj3O*Ks_GdOcN-3+?n4D+7g;OeyOEWO-"
    "3|%*hZU(2nmf!K*!OMepCr7^=PEU>xj@}%-"
    "`Dyz8=qIXi`xd``ee}N$sG2<*`gn~uT!zzT=AWI<rsw6i>2HM&jZWKD#Y5e%;aGp2UR|G~{q~oA5tb>uUZ#QvW!f2JEPa0`+qAz0"
    "ZhBcL>OE~U*g`xj<c?>NTr+&dG-"
    "2E{%BB2F|Ic+GdBe+Qzv0bO2qvxALgw)M=57dTZ}RL#I3Hb~M}h$*k3tR?^x9E7o>BXa5xP1$nO*#OM8^{VLw_AX2=jF+Bg`_oH0"
    "tJcv~*&l)6b2dl1Ti2jl^Hky$;iG)vex`*|Cr(Tuiu`F!ld1HetjF=NRufP0*KeIdA*Oe_%f}A1#)&dl~)eI;Aq7PlurA&TH+S_E"
    "x>UVXoz!6Vv$nw2{<>Zk=DBojrec6)r!Pt4%7uSjT}vVA|$r^I~NqWvM0Y{Z<VIrIl?2DWpzFfX`Y$+=UXRlvIh|6Es?}XVbwFbp"
    "!dwKc3%io)*@2+G3@p{n*1TfSuL5EHroFDv$wb#&bnIy=*sQXfmgtXStl=BP`gA#0zkA3caNlOkp@+q)$nUr@z4%&wiWIfTou;3z"
    "!x$ZLXb}E{yqd2z$7Q=H}b`IsWC~)zQnAHVpmZviUvK%U^$Y-*{i9ZT*Q=y=~ud`Z-"
    "+wJ_RVgphDjG2ncsNtJ9`*O_`p}KH@*9@xW-TS?AYkdi3T`Z;xL$W_Wt?^Wod$zfKQ-IeK~c=EdO+vpgp;yPBe9EZ*$=?Dr{Y+QR"
    ";m;Rv76E-b~_q7(BAu>ZzO^wJ8ux3tq6hDx{WG*&GZe6LJ5ire!cQ<^q@oGjMqd`e=tFkJlyH}q`UYuN^^o-"
    "TFzhT={;wT0UmeAc+6^eLQwEbA_*cT~N!r*P3#Mwl+PFBgNJPrHge7=CX~dhmyroYM2Ol6c^^Q;<|FIaKEyvsc1r66g8#=cXC~%>"
    "~4weC(!`*b{YRua55JY_vS6J$nECKSq$2-{y^PD}To)XmQlY%b4V4l(AmGS)=Ywq4|jP5991y-t$rGw$D!gtNrT*=_b7!-"
    "~C(yO<%n}8)4MrSsk}Bw&EYp8)>25t^3E;y6@r$L-VdJesIvjxG`%t2nv1ij$%wrYotrVW9~z*MM4BMYKUuNqGo6Fwz%9ZUeB-"
    "2TajM4xM83AzBWOOt~TB9fd-ZIX#BA*@$78&8@{)AU1KKRe|Y!q?eWRs%jsVZ5B}T%KJ@1u6{9?Qaq#NZU#B15ygNR8dGz9>yLf6"
    "?M1A`51MuS8>ASaoIi%9W+ph-"
    "u+nO2pL=L1yS#t>dWg?S@ZoXFIckJ0jKW~2G&nCS4Q9J`kX@8W<AJy^!z5LPONA{0pD5z0h7z3d54NdkAm~`;+OT!Y*A#@*GLE@}"
    "mzJ;l5%I>wDSW3m>!vM7PJ3vqS`9P|sZDF<PK)5DCFU4oN5TAA+1NouR+=(OTyx&;|q^FJOkk5g;?xHbx2%M~7R%-"
    "2R$_zSt)|w1bib4w50&P;d(|U@(zoV66KQ*;Ej~Asm|I}6u_~8p*f{cg{KEcoZdIMmz%`_ITVTIH|*akSI-bS{)Ug>O8?(l{a9E#"
    "TQhc{p*htq=(FON=cxWF5pW%^&`az^?L0YrCxn_d1|7S8e0DJ`p*nkgrz)%k(-ku7b17h0QAXl>fX)EX<cbspR5rqiz80-"
    "5}7_BYSZaw<~uaQXWM(BbJ7I@^&IG8=a;dE?=TvEc87@z9sFuxp#$>_(?U4(_Tn7qWGpYJ=YyJhbY1{_+VkGRiYJ5!l*M3$;h@#1"
    "G~NJ{l;<sGHT%oVq{4JU5Z$`KWWBqsDEMpK8uy&Kq|_9tQC6iG0YK+`q$64?1c}X7U!@z{hJJ95)g%`1+3vxmtVeaXStD#|KwbQ~"
    "2uU6K|I_W(OZ0LPlX@sL6xnRpo;R-"
    "Z#^Fv{=W@554X%&EW#l^q)P>4=seTgJ7+iKYtcy#6{0b`gJ;}oZFkMzZ39pS9)5O<7+>^(=@g?7wC?}fJF7h|0U&f^M8{PEVf;y@"
    "j9c+WNX=QCt@HD&(`h_S>SpaGCp0<rAv7K+2<bfHHILyn4TmOYTl@6yMsu9XneN|dn}`7(}o|jn=Ig+oE{&(|M2Q$`s1skH!r8}P"
    "mVvlIQejV@M`+u<mlDW$zQjTfi|8tZQ^OIufuYd`6?M$Oj3jW+bL-"
    "{L7{3{({TBDNCTkz9r9mJ<4QCK#%B&44VTj{2#CMZ<BPdz`AJ)QrhW03)7kZWI1gQ~K|{!?0HVVxeVU!N9fyKVuRh`H(`M;=+&*C"
    "Q{W^XT)A^@B<h3#Ry}Z!h22aB3eOA*8*|3vtbLqbp1Y;vD*-"
    "AWaWe+zwLo?;A+t_S{2eZ;+mTq2m<p40IVPSxKX1CmX91VTYT9E7c2-"
    "ABGmUu~~dfAsz*M(8IYRo$c(+HwFhTZ+OT#Z^GdOjMsrO~W{cl<tTt;DEZ;wQ4;!zl9TW>k9A#;eKMx3jY0k(;cceOtei)Q~8{X#"
    "0x`24-+ZoN7r02a|Q!b#3&b+aJRGoaY7x44!Isz(!As{BM|z>3|Fzo&0?CX4-"
    "~0rte?8eMjc*&0D(e3?yK)%~|0ETb^hlHmmlly|Io$%YP${Sp<d2(oELXcPanS-"
    "O~P^H&Ii_Z9OI4G;1vD>=FdJQBr^+OoAaS2V2qnl?*g_p8svwb1c{2R;)y?<je5hKmPGIiWs&Nx(qIHx*$=rVyj4&GJA6rBGM^wn"
    "RzbFbqi6&QkbB_)V1VDXD<pfIz?q02~M9N-UHF@W2dwEf=o7POJ&?3?W-"
    "{VwcYRN><RU_u?|aI*NH=q9{YXq6`6TPB`K7TT035vJnw8WrCLdr>0|(xP2zy`F4GleOa|f5c_9)8#dVX@`GCEHHj=jp?svWE`gh"
    "ZEb+Wt&{57(?03nmR!`y={gBB(<9(&e6*9oJ~8`D_wAk5R7orP@~X05O4AT7oX9mKEN8R>f0-"
    "Bx#_Z_SfezhBUZdr#E)K|(YCuIqbqd+nBZ{F7|D{Si_^sScNU+zooLFS8~oeHdc-z`wJwG+UmxY>7g28aUA5g9X*-"
    "S8WkH{v(#0+8!?g+T+1C)#{3`MY{j3mwP~@8US?nuE>KHcDa}jTiJe5+fd`UAJTAL`>l-"
    "Cjq~rz`^_)!(jSeN1Zsu!4%c~Omc#c|{^nPib_vIeY>)ABV{ovv%|_zlk;UHOUY6E)r>O9GR#Z|KgrWH6q(2uy)Ic}#Dn<A5xZsK"
    "ev@w}3m5Dhrr@gY`+5L8oAHAl-"
    "jh%&C>?3!B&pKPzZ@uWX9h&xgotN%ES^pN>F|DE5Vrs@uJ4!23#Klv4dCKc#OK$S{^y5bJ&@9vP!-q)Ee=mRWdoP-3;#oVwCY-Wy"
    "I9<Ttj{g4RpI$njGQZ}blFy%5^moXa8E6N;Er*6KRy0(LluDuDPcB2k;#2U0+pMWRhS$+1$*lsT5_A(Ek1;#ttI0L&kVCVooBV6&"
    "CSMkcZ0=FJ5#bwZ>3aWr>AFK-pAF7$Jek(sa<N_0zdf~cM`^(=O@-"
    "xt(#__=mvDO4gl9GmYxPo#l}nH}B^d0#1KaB;{&IMH^rxf4ms=WLJuGs+rXPAJ<J+~<&o~UJhH>Rm>70DFxj3rX&XS_L$f$%i-"
    "O;N=wMk1att<ekp;)?7)C)QoR27v-"
    "5u9$#2_^Deq>ILtSVHnz$q<2fqn9ei8cW8XCgsGWv0T%Ajd;Z#tbI^L;bW<SilS6si#8=QiBGjlK?kK{44JBz>gec>HYcen4Ugzx"
    ")vifl(=PfDQ>JQw#TKf(=DY~WQMf8PCh?V^S;0^v-"
    "pZ7ux3Ofism&p&>Mf^>Jbd9r>q6HxYs@BHPQa{W)n}$T=OLORtxgymX31%ggpAorbjDiC>M;h}9A1TZWQ+>SPj%|3#7UwujC4nlk"
    "CYXetq8?rs?JP{W@W@HRD|4Mi~?+fE@N?77N3Nq;)F~pBV6T>FDivaS9Lh!LJ6D+hh;6Y(p(rXy$X0-"
    "(^YzmE~2CBCm7vk#XW|_vk%-Eu$!o?%bGc+t#hH;9Ajk9?i)0oe!lJ!O}Z_S-s6(xyQW=-"
    "<$mAdqka=+a!Yp8?nt1&3wXt=?|=pHHOe)-`N8Hl4)T%+CbapwCFFVYX}|e6NIP7?N^N!`B{@Coj&^OTeLc*Q8>BY&$@@(f-"
    "e;P1N|JvkMypnA)LF4+tF$`<H=-"
    "n+G3Dlr7M&byrTuNCo%?t4W=_!M_1Pkmo6>UHS*Fy~=^#CCH=;^*K4jW{0_X1#z&r7S9g*v3wg{K$L8I1_jKU>mp<DAN&868wUCv"
    "o6a{W%=^X4_jowVbJ1}2S^aii1uXz0HwiK&^HJ~h1``%18}^++@y|5+B{bxLHQl%>zAb67tBP%hW%`eM^M_gOuCXGbmIUT&>Y#?N"
    "TE9;1Gf^7*qa8K~QFq^-mjIgM(cP18IgNAEwpJ3M}W_>y82>rXYa)3-"
    "X9?S2`y{JL8X%B<NmxBu^`&w?3A=bN)fLjWztFJ8SRn{c1=1JfCB!$6^z3)LqCP+S}B4L<9Daq|g!Mq7xpHqg{=Cr^9PnYQvj?R2"
    "eAxfmuSc4m(-"
    "NV)t>dsIt=vY6XuGkDsWzPBGv@cXrx46OP##Quy@Da3kLmZG#5EPwZns%v=u)=vGg9Q+Pm@{fO;SkVTrCU^3ao84hYo0p#CwrG)P"
    "PHpr;)od}{-"
    "2Vr`mEPF|6wB#fD!U&wKpmCZrppbK2tY7&rz7)p#~Lt|0lrj%?p$JSU5V^hpuIy?S*%K%txk_Gk4CTWLiJOzEA@S1HQ9L_-xcPm6"
    "sGIyuVA|6Y=e4e6Tw7+5n0L1jb#R^AcRPkQ87CSW}rDUlrRH=#E8>TeeEhDl}rsyO_?H=^6=*E$@GX^65;N{mp4>atm~8cD*Dt;!"
    "?>M>t!lF}S>H(5Xtn4251;UXjuHi#m#c}UlG(o63IZ#<H>p-"
    "Am`QZ?64ef)TV_S9UT8<xmB{D>golB`d%Dcge9K{uN006KK6HjEg3GKuk5+3Nl#q1v(!?4Wvz28yC9kqq!U?+Pp=xPO^{SSp4s#0"
    "6zJgs+`?X7(j?VQDHb-"
    ">^387sp_aVTbG(%X~p5hrTm1Wdr5N~6^lzF(Cikv=`^lN(*beP3N@u82Pr5#b(aH{Zj{yRQBZx0=hDWx@>jlri+<K>;?mne6W<UR"
    "j9`?ahvgcS_^C>ku5^t7RAOU6%lYt&hY(PHLCL+i3vGP{+*HvQ;r)}lu(^Aw}kjS7tZyfF0mr5t?<mvlgD$z+Kcf=HcyzW%(-"
    "MsJeZ(1fRx1(ex)*&MfSBE=V>5!mir^?jWlRg`KMZKx3MU%&nH;q>J2{mJz0n^%8r=p9^h6WO8%`15DO)4<bi6dRoQqpiuBPu6!3"
    "MLFHnvHcOnm2v|RlUT;fHa5HN=Bd6Xe>Cj9WdQs3;A_QZ9(|Vn8+P4$s1xw$ZPKscciDdZZoj$Q`9CW7@}%3yVybRq@M5ZWB=~%I"
    "*61m#M|3f!P8Yi%+PmY!<HMhh-k%(|lKSH9n-e;3y>2Z1SJ?;e!sHM-"
    "I=)QB?A9v^_R_a%BD=9YbaVX418Mgd*b|%1N6Y><Y&!R#*Q(a4>2CI-XdBWPRTNjT7L^jqmaYZEAS|alW4V?!l%$n2%5kNr3^;*("
    "r;?yMxs0y1<e+#$Lqc<#@CWB~-"
    "?z3U(4~DfGrCnZc&gXToG?MAovrTxQFpdxxFz?`X`1&i|MdPrwBrVjeDwN!ee1sm!M>mMr?NBGSDyx@&sMj5|Bx)H&WNrP%dg`iz"
    "EU9U-kAE49%<*vd}6osXuW^hm?232cwtE<k2WCt@2eVySJrwf8F!|D4~J5~l`XoRg-"
    ")ulT#U<JYpQDPY~~JdF^7_4ak0Rc2T*MLEj#=@c#C}$wtKuo`4)n$7|3Hq<#D`m19I7O!1kVz)+Sy%Uer(;L|Jc3G3pHJs5Pjgfn"
    "N6U#JfVLOPa7#q_lO_Lo`Um8!k>S+LOFZOzyD}Q@J4nYAuMmX3|Grs5XLJnSg~1bh%egmn3vsTy^762F7>uIEI_>R2!%dv$mh}n|"
    "U}tsC5#p?ua<5=|Xy@t@KP+gXVh*Jl-CeA7ZB4y7O(|rQ62x6mIrLd;JVdq#(Ca0}qkzxhl?O_@o$9F`2ICw2|%%*G?)pmOxjBrv"
    "!rvOD+YRhkSzm>S4s8-"
    "CSJ)1D@yxN~!5$AUdxXY79mN^b;;S3ui=xOIJQ?y6@4uWMy_PDh7YZERWxT!M_bKc(iDv7mt;;uYoP(SHl)Rn7ejrmzq1Gsw?Eu("
    "x=li01NWxO_C@X+otqXzf(I}zT)}t4NEh%GYDx$J-(RDPn!eeO$K0thv59?JK+-"
    "Qc3a<SFAzkH+Tha4V1PTigx<kuTTA!H?AprFkiw6a8|w3RpH__;xYlkv-"
    "&~dMDZODhEBm^uNJFn94S5IB(9`An8?<<{?&sd%#tNF<ystTU<lBH1YaQCJS0=f`w@<_JrjmNrlxOIDvyQ@PVHKy_)hm30uD-_PS"
    "b#BvfsR5Hx|uh@pV3XgESjq5%4yFzWq&?Fua^to#1}}1ATN_FKns0^l@_KbQ5~bSqEL($%-"
    "Q70CECJbNU;b}g)i_bDpi*}AcFa(4~y-"
    "=?R_Ku+u`Zv1eno<ZVY27%7Pcygr+0iOU`AGPI(ietCcPushQ45IZsFB@Cx)c6l;noB$+bW%nYzjgqx<T&`L5`1fjUi5M5cb=7xH"
    "}Fj_^o!jir|R#Y&ZkJXEvk7;#h85f!P4I3;UNub`p`1z0u{Z3yW9RGAgbtz7cKb-"
    "tbrKkJfygocRK6<hBDAsOhgnuP8@}4TcmC?aUX4x85zXhmV(1n?3IKcmm{*w~P#$V<zWtSi65XWfE+Ksy7z+D~HGs;*iHy-Mb?d%"
    "pVX+qgI^Wt_wDT9k5!pHL&70Z4kP|>6QED(A5<pHXd@{hgM2fVwUk1oRXyfv+(&b0n9_+>YILRpAS3fiwLDQI1N{^4P&rQ2waTnz"
    "@e0mzu~yW_(@y*m2o=ac)UYnkbq5Ka3TezwO9>!plsb>r(Nd<H3u+q?L!;GS)&w0}U+wgs8rWOgP8zZ@LBYO4J2zhyI)W32q?EYs"
    "Fbsi%W>AAKnLTh0nEihF31mPSdqUG0l?At=UcPC4^pfI&2nNeNZ!%8JEPKoU_0!=={W%&~JI8}vP5lIR3>N`{rf0cY@J!NbwBXnA"
    "5R0x(ssiwEejOqeRIcBVF{DgY$`%>hu^0Em;&V`nrL!$-"
    "8pgl7Otfyqo)oIA822@Dn{7}MVIeS|c=6?mvb!Fn*R5+=h}8x>~Cuml{XwaGweB`UyPpDSGmU+5BC!L4yV244kLkM-"
    "8&P=l7WSje`F!LpDHBnV5)E&A(Oa4|pu6ndYk<$={gI28EMP=!P$b;jck@Km8+!AmR-on{jz(`8L~zu{O}tTDj0c7TeK30);*HUV"
    "x^%+3ldg~ZAy2u1WMvW#y>rA*?iLexUgCQw7wMEoih<`rG~4!O&QrZY(cLBJyNXq15vMMlFCGGS@CwyH!d1lreVp4&)Qq1Ng-"
    "28HPfG@Svf9q69j<N=wPfO43W1tg=^Dq|t3$0T4nOLZZ0ZiMCn=o!M{+Pm2$T`-"
    "(kRaRFZZGqn#>54E+BuE_(8c^B^t(9X1v#Ld~!0p;{dUI1y4WcDXu$akIL&0}L^+ouA-$7+{u)zF~X^nmw$QXpf8E2t~f&o-"
    "F0<J+7Qt+{;gqeee$^?xDP|qP};~^&+)8?UL){vG9uQ54QGpIAewBr?6!Q$~t55B>;Hpv&*8PJ0il}j02u~;+^0Vz0Cz;Q1{#tWp"
    "bAX!Zal*6>hEFliE2In&tM`0av5?I6vUWP>hNiY>+<WxurOA7rJkwZ|0EKM)4tT0@d_zX*-"
    "v7{hEPz3A17cfblt_J3Td#nkj6yL?$CB!_%XjS~Dq7CAqw1Mt_sc@X=euJmP;9kVuwH_b-kHZ&Km;1-"
    "RPG20nJ9t6Wx_>(8&St;;aI&bV{nO!_!{bG%zTs<Sn+kP(v3%*`9Q|QmkNfcTJG>WQaQgD-"
    "{kwyc7e7y5AH9Fy6a)PE;Fum<T)1+4a`dNz7ijnGTYT>qs)PY;))qF=R~QY*lLnh4_nUGMIYl@G&ka=}fjdzZ*3;6x*i;sz$PBjm"
    "?B3yAJL)SRjoux+f8Sh0BuBH$(bhs8iy8picvV+pU=^rrih=GJ(A{2|=`NZ?7kr#e7kF)Xe?XV)M+Gv@W+6X{H}xd6+ZtY>P*jIv"
    "g*<JZo1U|t&i^3tM0dz6h;PfIRyS9>SamL6%GvCqxo74R@a!dBz5#OrHnOZgvAKM}jY1WY3QmAs8P(SMKP!|k)+LXPt}jS^mvtzX"
    "DNW7AYBZ!WKEM7P%jHe>*6_3T9-"
    "?I(h)qfhTkx(`?KLBCeE8x0;f<3*==6Q7Hqg5lt37R2d)ipE>0*PT&3S0<!rB|#yK4(%r7qiQ=LTnXnnQn78SmSmc()Jg8)h&6B1"
    "N-"
    "yh7#RP8C^|~*2MIl<*xhf29=`Pn=PArwM+gd2}$;z0e1A5e8uQLuFG{9!IGXg6SmE1F1>KG9ookc2jPNY+;LY|y|`mb3>`1N(K)M"
    "D_eKN9ajP$u<J+%sq&Ghzw0S-otUxTkV=kv;b+;U*-CJ=fv#cJ~p_BzOSc`*h055-"
    "xzc$Nl^bsWT;#22TN2#2hjrv{ng;Tx_e05Lk?6lXQ%c`Hg85p(e4wK*EFzw(j+2Oi(pmR?i@-"
    "|Gld8>EXtEMO4O8JRh!n#kt6Wo^;9h#uUp^Qb{tK-A}_;7T*wczKz%A77tProJo*x=z)#BuqSB3sLDKicI#!A^Pux?#jl@yNJC-G"
    "jWm$3`Z<VGL&}Vi>8mXEA~m5zrM4=vKS|T#}kQC9^HuYR-a8frp}l54^-"
    "+y)$7?yU5=}9Q@JiyepD?C#l+I`qbV&)q%Bt>PXc+(PX`Dc<u1gzhk_<v}Ey?_{&%2^N-2L8_^NMdAG+(6-"
    ")ps&QI^EwF00>hb8;Z^L4XQokXm><Ke(?C2q66&%fLRFP~4Z=p?~Tp6_cx#O>YfQO+*?UC@Vn?S+rqm-KVm-"
    "3?u61UtfmdmTR5a5;FN`mwi6!0l{i+m88aSN_m*{9nZQ<Jl~NtkIR2Pmmjk2D&#-`a5ur58odi9KZN^did(-"
    "r=#ur;SYnpa=g51_Qu)I!4-"
    "h}1VFd7Ia%Do@Go%FM?YhWYh!6<4&J;RcZuISd(QQnHw1gog&p*@p@osF7Y(l;jP7o>+;zoneODu#yGz{7TRLL6ygV(JQ`$#bTz1"
    "?QGgw@FjoEIim`$jx)pS;;O$u+Bp3OeuKX|><&kf}1s+%nfAg>o-@8x;0hTYw*WJIZG)^reGdwKBFCI{6#);f@@-"
    "}}vzMX%>DPK|3>N=<hQ`LZAFoyCibuiGoS;nvRava@Dd=ATY42(O{>W7>iH(}xpyh3Wf4_=J}S5a_qZ)0c1m^5*@?@!`SiEwx?zu"
    "7~&YWvEvVu={sKyVi{VpjiB{{?;E{!sX6EJgJrJ;{tuWQvJ(Tlik4pKJdmO+TUJ3=P<aG`9fSy<Jm0zI-mCaUc7T?H`SW0lhX@`;"
    "#PaPY3**aKJ#+kKzy<qHGDoj>y3}@6lI_V;cNy9bba1-"
    "`$BCh&*7e0!PR&%tBZT0+w#Ykvv@tf+ECE$#v)ucY;12T{+K&&FbTg++RJbCzkrT4^x~?}P37=}A(pe|SZ@=^Ze8=ILf4cpsvHjX"
    "0+x~5?moeVgs$F;tk<@8^|tb&)5R(*J@=N|33ko=-H-e(s;w-BK1N@|uVuU(-ll7h2jK~N`VV$bJE-6uX~SJJ_Aj6|+hqT%`z&@-"
    "yPEiM6AA!AI&FyP<k?>ij!veSlfN7suTg*d)b?NB5QsZ;<{K*5zvYgO{c`LFLC1dvL$GP-_r70pIlh{WFU)xP(s8>@I_YC02d`ee"
    "{mbFY>AT~%uirK{;m22RU;LSZVE;N-hR$c#muck+NV+#@u%X&SbsuA*9u`-iuMMzsk8FE4e-"
    "l?v=hvT!v@h{Bp1GP$FHCnaYLjSs=i;uKMzab$zKEu<HS8o^MMMoO>al|{|9k*myeLS$`lXh*Z~E4c2k#GG9lbeRes2xK0}B98oz"
    "7Q`>|%tg_bug8!}S@-<DU+WUQOxBrglL6V<7p3E=n8lin}fqn_#M@-L+K*FJ2tJJ2`+5PKkJ|x&-"
    "soF2Rfk7;_xKUvguH`mo7*otY&dZ6036SN<uI=AQqNSE%l5!~ctDs@b6BE*qhfkcpxlS0}TGQqrkm9=*>s7h$aw(KuT~E+q-"
    "6Jsm&Ef@PhB*PO}BQ%O&>^WW~hja#!g?rvS1Jo-"
    "k;r#Wu6P#`MAv)1EBUx4{7*Wr1r=zJ?zjDEGW&&TYiv#+$D{#uP*FAc}&3th8F^{|>Wzk#GL_s-"
    "+#;wqF|Pdo6@s&4c*Q(n=f5sOXtE`x5DM+e<}F|=(5DV2+>fay3`D)#Gc3i|sM4|X|O@kMMrz&dWH<j%7dD<-"
    "!|Vs8gB9SmfSsVY;-"
    "<Gr!l{pg%cOk_CkZlCNO)ALcBU40s4Y_@Z~xY}}Xx}v=V^nA8>qFaT0dD`HH{oee!VPE)*_+e!RZ_W0Ee02#MtK%8S)IfN*J#(Mq"
    "7Ts5t6S=H72;C2KtxNlq9X!)yE^l~n!*Tf^<d^^umi)(~S4Sr|(d_m(^C0@x>;C+=(<`je>Z5DXIJUz{jlndo3wW=1`%5cW_phrc"
    "W~Ie#Sq95JxNW`tHgM?9Lwy<)v(nsMH_tz~v5n^Ri<kr!q_GJI!Wv~#$cY;fvri=wY_L)}o-"
    "&>HFxte*L{u!`Y0n*FUdJu{e9UeEdV5Ky<35-1{A_kL>7Z%H-"
    "M;DKMvtCNfTE&`RXo+CwN};wm<6AzwoymrtE7YJF41{!I>8%CtzHP{ov7B^VEi|80RG!Z2z@kI{#U}7UCw5E;AfC{M{wiQX}N4Rw"
    "&=#TpU7LjXm6apEuFJ_6U6`Yb6eb|J1jb|Q=bdvV4TiBk1uCubPy6#_xIrgD~)Y@MTdm%dp;K^vhCn4)!}wTl<i}Ks~Z;JaetVRF"
    "EHa0hj+*i(6DhrgdxETy3dvqwTc_>GM`@sKyHPMYc%J@Vi3!54c7gve1tI0Pyari)v=VLJR@lz4KAbDesf>DKd@Rja(NZpDst`5N"
    "q1dXWEgG6uxqD`Zhq$;1gW`Ba5#Z&JM;PJ&6K3J&x=^(&qwc1-"
    "X0&lICwSfW2gsjUQXK%PZtM?>2Uwy|2%y0p(`3Nz`DPP@yo;aM?W>czP`Me&D&I=r5%_KV~B%pt|dF&T1D!Mm~I4xz2fZyu-"
    "?fRSCgRzBfPC|-"
    "vB(lV_;tgBzCR!d8A*b(bo3$5j`(*&ap}@Trs>v?Wu|)Z*Je^DMetS3`i%K2M+XxXDSbr1pK}?lCknH4jUgmJ^xBL=LW#RkY;CJZ"
    "iO-{M!OyEFXFh7!Gl$-vVbaUAAThyax;=OJ)Q3ligZwG+kF&$UFaqvwFnbF**W7a(WwrNwY}I1HEs-LV4^CV_Gr1`yNI>6#lVMk8"
    "CSvS>bTc~N4-O(V<xW-{<`KS)x+K7a;Q)5EysOZcLsL4&Ru-^ecm|J?wjAd-"
    "y9D*`qkWL*XWZ)c$PM1X;ZpzeqV^uR4`*+q%k>g;X_h}!BYeYPvUt{UNDnVvRp?)9;r&DiU>g#Uqz7lyA!?Li9Ub!=o$Xj{qXu_l"
    "s97Fk8;!tkJ27mxy@f+eZnI*Lm7Rjpq;7ahKI}9eBSBC=zKQL*IjvvaiXyP)sRnac+tLM4&Bg}=W%w5I6Q%GUu^2F)Jwh*RKOwtF"
    "g5=8D|z*H-j?NimlSbJC}DFP0naZwK3azW8$Ro1WBABMpFgn6H-v6&@;2atz5?@-"
    "a?jJOP2_BXa?R8<SF5(WyHiZc#q1J4(Dr3h0epL*<MtNV`=O0)wzt1?-voVk0K5%%Y!i@wvvj6^3T*T3;)I-"
    "(PMnIFnjl%0tV+w_hK+EE=^D6p(dHDWY=o~;D#^1Djs@YJRnG2XU*aK7{tiFBmkX3^yHDOTfbEGTh98ID`lOEgQDG>HT@k1zC$Dd"
    "GC;r==_kFlCgja%fT-"
    "0`0vfO6FvT=^94x;rNtxbWqIGum3RE*vuEc1PC&BnM4zYRI>mLg%Bd=wUSe0=bi&Fod);ZM4nmS}x|4fjo37ke4uw{hRdX1+SOtb"
    "8!58+-R{xR3j0s6Nzn+%|<zlT*5>secbo@r{~!!(Vqc<;T{fEYR~0U-+#?-"
    "wq%*f#iFe{ie8B*Y<d6&%TbuUronrE#uXEwCV^hKzz=x7DoSc{<TTaeXPA*%W7-3D{ptq8;rgkQ>F3EMqk`*^zDsGh)-"
    "elZ^H|BoBd(0zK!7I{jKmLTG~E&`#1Po+xl+t_iFJ66+Qac(B#>hw<lD?|DL7xU-ud1i@*k~aQM8_u37ihfn!)^IlS!JBDZo+-"
    ">~TBuB>3G_n%5QyZW?<n{Aq=M-^TJxF*Ljph?T^qLrW-{7NpDO_lwNChFI0oOM=x7;^l^yvnWq<M|FC;D(D?)HfXec=U$yQPzA6-"
    ";G#o7{Y!@#Rgom5{O!~Kb+xZa&X_RZ_2;i7}Nguocbn)c7Hi9%Tg^rzWwm#yYc_(aK9_By>8==yB-cL(KaLhWAl}THNPL|@5N(qP"
    "=A<7_6Mgs^wYAG*wJF3qqmVPEs=oc{Oq@8t9SRk+fDMz!xu;IF<G18Kf9-"
    "C?&a@^;y$;)gZr53^={r}vX9=J9RAc^yEJ`w*!r+1ubG5_r*J+yZ#1Um2(!ycaZD9eO0F^)8?w)mE=!a6nR!!9bTE-"
    "7L=lqkDKV)TmtJJ2@cSyo_xk4F>zi+`Z@%{)^Fc)zy4<|)YjrA#9Hch7+LD9fNm?f~w+Vl6?%-^-Ex}b8Yi7)7AG}P`F-"
    "M+x|3}}~if^h~tL90&qUcDoF^~qXVl4^^m9fk|0f|^HtW;df8cNd28ATJCS@usbml~SYRNkcXY3=pEgSCI`m6`kRFIfeGJvaLL=%"
    "Y#d@2gxX95n9E2n?q8u}7iy-(}yQ@Ces{GGlnL^GOltk`u8AAE8y4#|T@>bTJG@Kn2c<P7JcbAOqg(!iBItR&TteTS_-Tb7mP++S"
    "pi9Hi>Ss)SAmIEpsvm$DO3|0LEf&3ZQzTLIPD#1pu9N)cFQ9AJ*9J?;8B@^62DNVE*WlJ%8q4MjTyTfDaRpd(BV_4&4n<SXdyQ0r"
    "kCrO}CoWk~ve#<HcM<0$u%f&a-_RxAZ>Rgg<}wXe;~uuHf%?1%JOQ_}}iXV2XWQmGiFlz@{>j9~-)Nef6oMvBP-FEm4l2W@m8F$E"
    "5-d;^ptq-Z1V-{F$vi^QXRy#o7lq!lv(=48fx&Ttg=Tm*I?EYo!c>Mt!6t)GG={GzBC!J^;TwLkI7-"
    "p|H3ek#4woSYGe!0_f!Qzq+gNfNsFDnzrw_p7$GHgWIl>@vB65h|g{da)q<s!te8GSGMNzvZSV<<h08cUIe>tuTgUwthyQVqAiI&"
    "v@lwP7TUz8=Zh0QE2V=Lhg(m}ygg&QGQ1JN&t~tVhplv}AKe8xrppS;<)~+Zqrn(gHm;v8vexx=+Vu5@kByMfg|e-"
    "bY>lq1&I5&)+SAp8q~qn)$o=#*6HYOZ=fnGp#`AL4_V)Q`Bawf;oT2BVH9q=$)Ec?xD`%OXkCu$EU6ZTd%GsAPT3m|IU9GgzwQfv"
    "pog2Sc#nEyVH<ZKi<99zFygww2F-"
    "KcxW!kQ3TZwWdUa0Q6KhaOur+?aK!}r{086CVmRQSv#50@AO9JLJ61ZRNZ6LTy8r2=Qy#6eYDNrD5O0BOR7E1{fVf&+{7cO<MbtG"
    "0*ZzK6?v{cUN<+s5=gtoYDexb3U(6kK|}t-"
    "DTWJ!x&5@3DeEI9Bi#kmiqA+fSdv<*#e_=D1y`{$oNYpD(U%KJhlr;StxN%i$7dZN@hH1)&exx$I7l#l;XifI1~*SXAeI5aL|;vN"
    "*fC!W5MB>!`Z`<6m(dHUrUlp(_%vN_UKT2*O8)%at1)w?4W_V#%XOho1<=w03Ybfa|*g*9F9yE$8DYfa^BUI;?=x4Wc*ZtLghxL1"
    "!T;ByyvL;e9?l-9ALMU*%-`3PjzCNC(H&yV@9iuF*2XzvW1aX;{`-"
    "TpZlL0r^H>_z(DJ6Y^W#4OZ+<ba&gB?vL+yVN6P(Hu5OmF<G49TzG($VzXD=vFNy0j!P{C(}vPUWQsP*?2GoB@!f4KZ5zT{9m{?*"
    "eEu!=h`(N)!>+N_8coXs@Q*Gz{FMM&N<c4?SI`<rx-(TP=h1gzlL5-g+(G2EFQG&pq78;KYo)Tu7G|Id-"
    "!4FV^vIq+b2>1mm<TGcByF|26mG1p%3D?{V*!#L8Q5V|f+?Xn5T8iNdI{QB)ILg2Ki@|g?mg7d{=O^qeOK!HuGIHksqec||J=J$-"
    "*;!8cz5PP82L}LMRSwsK3^UzSuIK0lnQ;`7SJCX)s@MAe&gDRyS8k;#XXpAq$|u}v{HM1czwWf^v#^kug|W=5z^An*v%=}yx&2R("
    "r<dSFPdJ2-_K?tuW8+#J0kK<&P;N-"
    "%eKhl%K3NlzuV?U)1~h_98bH$aqD_K1<Tyn;8XMPuSWX6v*`PcY@g6&k7rpQ4{pA11l%$Q4Jv4&{o?`d8@C$)EBghV*ZSsn0B+)<"
    "eg}X6=JPf1K=ZZ%8x6t29}kf3!b2<DHOrlj)uKQB$*8+Q)CQP1+65zZ>vcOwTE#<RH$1f8jf5<c<B5j~4hU0OX~%$Nt2Bjkw2i?r"
    "pA3wp@WR;a6UCaCFQAJ?;m2p&0oAU%33rU@$$->jPWFC0n?*n<y1TW#7O9J&uW9Xzw{K344_=&1e-"
    "TeqAs&4hoF47!2(BFgyscM@(~i^kCz!$)Pg#NYQT;qQeEsh2G5Xne_~^}x_PKAi&;R4?5n1lT_eU>3Z0Yc~d*VB}$UzD;6H;^QrS"
    "vs>ouZ|%m;tIo-"
    "?%A4qZ`>cUu~!*NydG_zc%cA;(KwIadQuH)AYg1gLfxKzZ_2cE13^p9sP9l<16a%o43=KhbM<GP7d(*mC=28^YZX`aRmrQ{)^~W1"
    "K)djc=!$<|8nr^=w<u-"
    "@!@}bI67`_L0<8+hwl!Kj+dWe9R2)|M9t~e<zW)ybat7^^U(z^zlfh2%WzDCS)4OI7z$wL9B1?8EqKdZPqfv$@kL3`<=a<P6>qym"
    "De&nw@mp<WaX-;=?f-lGHz&_zs{cQGZ?+uAk)`Xt3XIppE}sXUD~N<7?50Q_092LQdRv;0V(tQvJV-ziyRF{+tmQFB&Ol<4N>(M2"
    "nUN9h9zOh^`x-"
    "KCS(6wv&q6R~BngB#lLOZ&DFGdU7{)@5kx?79H(G1x)FSDeagTIdk2kLjqr%eU8T2`u%I2ve(PUVDGW<w04o?gWo~bf}9!aI4f&-"
    "~037o;{hNgJ)DpL>FS{Nu^S|5b>+NzjM3Nk02i4)$zQ=AHc8z_Z`B`Ik@0*9HzJjc`i-Wt@U$X-|q-"
    "t<nmN56nxe_QgG<2RtpfE_08kJRN$au-uj67wdH`N$P}(*CHK#fInUUDRq&7&pD3)A{z|q8eS-IPk*7?R@%MTD;vP&#osfx~~|cw"
    "JAi8KQJex#|+`9VCG{w!Q_<lx+~+u`=J=tE#LKkJbni+3|`*J2h7&f57N`cBy1<`Uafb*A5<s&u*p~XTN-"
    "<}b~`>RL;BozfWO|@X{zs=FaGEB<LC3^f33!u|M{;q)8&7?dh=heKJm#Xn8!}umTTaTr^i2>oSoN-"
    ">HE{;<Nt&UU;o#d8M535X4Hi%%J0@pp4AT*zArz!(?niw_#eloAC6)As4M&Z_a|>pU_JZgzh3=oQ_PHm<NDkG=K!Oe|5|n4ezuD?"
    "!bMpc=Lh!=t%oiJ6_qpzUP}ydq^XOGgDO;e$8Jp)jW%Y|W9JX4dgi3=fGct9zB2grgNoPJk0v=^KaNlw=R)h!j5NY=4=Em&K49r)"
    "T(9t>-__lxU0i;17q^wF`~LI$_lVp_r{^a}?{P-E!Z{4oU@dfNQ0`Wjuh`?@W=-"
    "7iY7v9dtkrVEXf8jz|M=a}`$L>YD=_S(A$HB!fWeoluj<^zB`D$yK%%#dc5_6hm+KWB$sLQ<eUYaZ>B?QEl3AdRHuHbyl{e4u%CG"
    "L`O9^Oy;Y!_V`2AZm#1CilzcmZV-w>POuS>?>-~OjtC#UgWe`^Qp-"
    "$rA!DbC;iXQcZ7^|uWronPGk3I$wozs2io{Mus8EWfKtF{$zxmUjE{6(%Y1zuHM@;h9xT*6QaYh1Gpn6zv+Mcr#jZ*V4zDo;SYFo"
    "q=O~qjlHbm50X9xZ7R+)wJ^*#xbbZ|L%{C##U4e_jalWPR8A4xinojd(6YM%9ap{zP!DuwI56zW!v@l>uDF+bn*Dn*bM=k78b%*e"
    "#UE8lFjcPt7+Jex6QpcD#>5e#`fRGiO=~s(FCh=lsN`MRPgYA1r;&^J}Vc3RLWaPbfSi78;JsXkHk5lnTwu<$e!<U;=OD3@8iV3="
    "5Zp%9{_}#-h8<%fxc?{sP-"
    "7CcOLlMjuP8I@Xe%hk#;yjTy_$Pyj#3!biYY5W;=hrXNp}r)RiwaP{TIZ>KL)E`jS^aZjP;v6%W5Z`Nu9ti*&oA#bw>AD;^s4?cM"
    "6CSxS13JRG*jveUvX3c6pF^r(yTpIzzPvwmB2nFp)tQ27j>`mh3z)?w0{yroU<?`$<yL0g+>k`gtLkwGWxLI%xEGH4P>DRo|<S_;"
    "`)pPZ2?_?S??Jdhgg*-"
    "eZ~d~eU57b9u+UCv$yL=RmUc)uaL;TRuhvqdkB%sn)#4T^i4qIAYn0cDn1XC<T%cyi0V5tM|$lxLPGuM^ZRDgAu)_#S-"
    "A?mcGq;+}Tz{sp4(zHj-@%O-uZwf>-K+}aO5!n57Y?0S7FKVD<U8T|CL`sMM(^w)YNzaKleub^0e19jOH<>2dVesc(|@b%!=+Y-"
    "p=<_qY|jd?A%#fNUbn53=}4?z%hXsCM0g7;mo>`lz2D#dP<Uh3l8!Gh2p=%v?V=;(#ns__B(tHbl@QK+roVSR?abl?uUH*gTAbGU"
    "c-asVy(Sf^@@U@fscdTqZcVc}u}Hiw9<^U%=crOu$T$th%HCOPDoHO$)Z(#UJ146LqqZA$vv@yyx#kLQQg{`$%Llk;D8ff}+K)bz"
    "usj9$URAWd1K>jxeVAGi`|Ru=Mkq)yp3Px1Z@@wR;O!&zC@1sG;3UyxngQW$Q^flvZHWNe0YH(BA7AdU)jc($Mp7`n{DUpaLoY08"
    "Db7#^Oe_?#^Q?_IaouNaLAR3hgzfFLrUBol{QQV=ViL?xNz@CQyMNGs00R*5pss1H7nSXqy8#ubP?2O0(x9Z6a0;I$JbQxBqyWJN"
    ")?sVJ!Opm?O?%(!F&9z`VP!<{nGG{d5mB0Gqk#oulf2C6&GtqmmaFN5mzHls1r%hld&*R7F6CENPJrTb%gd3$*XH@cpE{dQ30LTe"
    "VKe%_qfHLSqD&bsV6)mWKbEW7w3{p!NEgOfA%x05qiU1k@UArEd|neH$7#c(+Ga`<*R={F?d**LNEjknh4<7u2;tEp(Oxp=yFRA*"
    "kE&PVAw(afk7l%r-"
    "DEywud$2Kck$WPxiR%>&&Tn8;wy#G2DzU<|2e*G$3&*t;PHgDhXQVcq<U282%40?L}J!qC6&v76298~dPWky%My7}@qmi_>BpD?F"
    "tojVXiQ$cC5p<L^lQjeq=jM!hxr}Kj<3><v>trsg6V4>rsW@N*Q#McyNWwooSGbvK9v9YNK-"
    "+WTW@dV8|%T!W5c7k@mwN(xpAY*1H5QD&BwUDlDbmlwezpfuX8e@xHU{4v5Rt)LkYhDx5YExf*)>>>-"
    "%STgU!{<J@4qGxmFNiT6oh33-iRy^*B!mwj7rX%FpyBycde0(Z(&!+9G8kFM$zZr}F33QivlzQ~-"
    "Cn;^PB`@FN=ar1chQzXQDtOV3D1ZyT!QrS+*uZ~r@}->auyg-BrvZ{36G?;)I@<~6PiZLX-"
    "<yeE)z;N&~7FQmnG+#G4CX(GGDf^JchW59$zs}LBOA&*eVg0rNLk#QU)tI;ZhkH5<HDDNfi7%S|g<-"
    "7>p@;?^229gQ4%D<|@l1r0_C%#dUy6ffx<h(X5T-"
    "IeF<#QaY+2thO?zq+JA6iP2*`I;~KtyogdspCtSsgN$U%WGiV37zio_j{BL0NN$7$RVoEMmg^XBJC9PMInl%tP{o{BB?*CtMhxcy"
    ")s7w-"
    "*lU4tZJ>!Tf{|AlN|Qoh4B7<Wh=3~vi7Y~|N<mtZ49IQobTG_BtG$&;a`;1pwn?fObQ&iO$YleM!MH7)Qc99@6csoWk$VD_7R10?"
    "hvym!Z_j07D0Eg(&Cr!Slv8l3F$|La3n}cz?DY0(-v79t7I&ov-"
    "|JpwlasH+KZmt_X&m)xUcD~%=(TOZ(fjw4?@o_Cy#4X`Z1U;o?Ch?(z0)ey`aaa{FnND1zwR!(bnr6&=oI@{sV})<W$0ed-"
    "c=&vh0EpxP1pJCE|c|L6Zf5acg?(6wfOSA)mA60SN#!s-"
    "u3153VK9!^jxGuCmtRs+j8etFp{rrYrL+V3+nKuV|tpu?tRp>Z}Xd4P*&0vt{iCT>eFf)wiVF>((K;I7(JfCrC~wO^%-"
    "J0cC^)6z=xGpTcpv&4hq-2Jb)gK-Ge32Rd=W{b6w32<L%cA6vm*+(CzAGNL82c7nr`?^+lD;wp>};{;vS8<9{5#{fvWTy(xc-VNI"
    "30To0w&wvcnsLC(SD?feF4t9@^6V)72a2EDwavED>BK(N{!Zi18c1g@P_ckHEPU%^E4f?_o&HY-"
    "(~zP(|w<ugi|(Qqn4i{WZkUAcvB+1<cx`AB+LdRx9BvjO3@DfkQ7SsxbokvG@dhre0W91oZ_y<VM1D{{?wZ$ME~VznYk0th(Ztq?"
    "Sbcdy_NQKPK_aZG^tb(RCKWyLX8s)`1rcudb4@9tf<*ZXh?+XK?X0Bs0Aa3<ym;ADw5KA7YUONrPl0Slv-7>yF()OZ3FA{2naAk-"
    "8)3E&+@G=ON55&(w7WF{%b9k9|^5rA_6Q%uHKp@hX~OorzGz5?|@tEiIVG8#*qR>>skWu{O;8$2~YlFVfq;q7Lv;2WnA!4x1~3;@"
    "1L1|6zXVg@A*7zmX)%9+Pd2-"
    "zxCV&w7!+|39F=pw+I%4Yb=0j=?vEwoCOlp~t~V6&*W%v`Ww0J37#7NdO{faH*XBQ>+0E5``jo&nto5eNojg~ti`@{cYa1e@w<qP"
    "HCP0jd!IH9xIEr1AZhVOa6%AIwI>J?95vl7+3y^+?h>Z`NDDHG=dP$h|QLyyANO00q_QAY2+=ub_j47dI5ruWPPpvAEWmsM~6AY~"
    "R};H$|;}D<8Rorpp|By||q>e$`KbA5A?bRdvU2XETG0+iTndtM(f@;vQDdhmO_nyKR%MJ{4K`W+}ytZqxuhzV#0I7j88eD)rl{4P"
    "DwBj^18(VXr&XFSfQ@Sv;R<9JUWDzwpDxVX-"
    "@=*#;f3caNLCIYOP6^R_&_24cWKr?(gGx^H9DjPAw@r1kXgPb$4(1Mj(aF59zQY60q?0;t9Foq`oukV!rLF44hlmn$Gr%G9`9mm#"
    "@ED1QYxToUAM01LRFg_;4&4T*zpAdc~1S?ZI%?*pUVwu1)Du|sj62Wae4*N2z(Yo7jaM@ZvBEVb!*qom`WFsnr5G8iU_kBKD}tdS"
    ";z@DxN*jqyW?WjtsdK`sjFnYD&_$)7V`+`Ddo7oH@l3FTgT;VG0iD+gF28T=PhGJrI;EJ`L_6f}BGP3BTN16SvqFmNDKjzYaPT%d"
    "p|fC;don5Bbw%q5bj%)-"
    "$O1%QSyKFLH?76vdx(^v?_XV0P4d}2U3Hb{m5K>{;A(?A&sc#uMQCMj8+UDlqG%!ok0WSJG+&jHjPPLG}g<ZO!<Vg4J;(>Jxxe=~"
    "i->f@&o1}V;8gHTbEcw1<rT^0%~wAU0z{S_BITax)TU7^i3%sSKg{5H+^Z^6D5-Za9il5cDACd0J0pl22i1-"
    "dQa1AluJFVY~ValKjkZL1yRhr^+&(pwn6kIb_2^lIAonSBr-8t0#Db!&SD(mSE)&PA@`;25Sxn%?gJ@U^@?SR=t-"
    "FV)<m1DjKPmxqEpizAw`j@r^XY$YNsHR<Yc%NV8BQ_hARft5EMjD;nyvUiUfEEZ4X_5oX)32DKOZCgNEL2*4s!<L;lSXV_~E_!W#"
    ";0~_R?*~7#-qh9}48u4EjH*vws(JO>a`x%4qu;ffvy$2MKhce##5OEfSGIOAhjpk?g}{U-"
    "v_~sV_V5XO)_eF~2#DN+fF8<XZl}GcZTaU}TFvcH)5oQs$FiRrmtnA$HtfR`qoB1@b|z$lViQ!Qph2VUSI{g0Fa&04%ETnJHZn{|"
    "L#<L&5uu;88^gWp24Y<TKMAU>48%IcF_j%?Xcm$&UQ%T!CYK0AkqC?g=n@0KR@Bmigbz%V{8|!(x6Ir+8Mu#_l`YCZG2<Q!c(Nda"
    "qfvV<jdy}L#(+FDU;u^xm2_neZq7wE*3f9Z6gs3Vi6b;p<+ZiS1AS@BHK2?nzzB)~0!2!KDoNJL0Z*iq;vr7dno&S646F-"
    "H0VU1E6^CA+I6QnJ7~3~QOn8W=6Cz}&A3_`h0yB>AAa(X|8xQaTtOMW&Fc3`yN>N4t^`YM`(*`&Xuu+%*HHVjvW^c^G{qbKpxd4P"
    "kMBvzJ-dPTyCx8GG+(BciJTCBb$#Me^MjuybJFJLt)N%!^=%RI+C$G>ES^4Y$o(yz4sJ}@W02az=qf$H(xC$6I0BNb`$Ug1X-"
    "{ji;-Uc#T!an~7qoI1(!i}ZT1(nTx0tMN^#Pq638d2nO>pa<AF_<zR6L_|FMX6m-"
    "+B&x}rXK})TC`~7Y>#*fhBj6%uUneggemk{VoI$t+n%u_r3^b#3n>fDw-ioFLw3o{?@0DLQNoYMNAJ&nJbZV2cJf0pz=A3B3Yx7K"
    "qWg=x#^|lEN_Ah~%x<8`7AFQ+Zy28SkFTuaK_(3T*o3&MeqdoGv5VLD#kPjkcYAs%Z8)%^?5x1PI@DF=AO=Wfp1wLP{YCMY>&1&M"
    "6WC!Bq82*z)S<m(9l;Vv9A?Kl{?$+Kj+?X08f+TQsH0%w1o-"
    "vKw|SW;!<Q8PSqyI{^Wd&J$QU9}xdr@Z`rk08;!IXYP=z7iPF)i`dzybK5!%tNtoVnAo37ys&RnMM$f5zEv3=LQ@n>V$&2>aE9&V"
    "37KjW>YZQ*BF)aTDW!+Jh0`V5}^=;Sl@A9^FR2l?nck(>*VwxIEWPPFr&KQX$C0cbJ8N+O+BA!`5t#~oorQO~#(&l!I1UANb-"
    "j35F_7(v1l^g40TDT=xDtTHi@m;oLVbwnoXm1I^iOkQqywm>%}V{{6_2xGJez+c?UL_mi#mj!oJ5TkUWkvpBZGYZok=a^)K>zwu!"
    ")1+he>=aSVLlL-8oMr*+q<BC(Dk_4F5;#gG7ATW|QJIMdIHCY{D7W4@Qu3Ln2v}pIp-"
    "f?$&`|PG!x|$n6}QnO%FIaiLI9A3?6_7ms^p0VI<)_0hAo+4BoE43_3Dih>u93NKJxf5vGi=EHAPv46ZL}HH=m!v#P!F>Ca1n(yJ"
    "tI|fgbnpq^;FTl;{@pdO2&a?Aehty<rm4#YJPcUI&!fFIEiBx?ZpL#CUzs;N9zkmgXu6w!m!92_trJOIbk@<0k1~f{tKgIZ{-"
    "IP6IgZ;c#1$H3+;lL<}4`UOGoKjf&{dg}S;bMq+iR=vuti{%g$3E**NBzzgWP_%~DCT~MKML+N>-"
    "c#MFB;%Pj@>!X)K06kDBcu>Lv%=UdEV$A)K-"
    "~s$lcHEEI5e%N2|H)3ZeG)wAd{EjJdBoF^I+su5dXkMzS{n&EHzY&6O%_xu4>Wpbtl^;b(fXgm$CNP@9jMvJ0!f7N9L%$JJ-Kh)_"
    "TqYCZ199A^hr<fkxH6`l$0itWa8l?lDvUC2tmD|ghUgJav;*-"
    "fs7Zw5kb&#!U5bQ;eyR*lI20~8%EL0i`WFWLX)UqdB#9hUTN+H%={M70S5}SL*Ozf;}sFyXc?pk)MGR&7L;%r!-"
    "WRI6cAHRI$$J*9CDI?8`(s@JtEW-ZBdQA6iA((hgEDE>p9`k^!zxL;GGW#Dmh<&KXUbaQjw1$(@n3t&HYspfAvo5A|^bLa<7WIP0"
    "Y`3`>9DGS(2+3bBKw*#VkvyGJ&ez@B@0MuQ(fE{WF097rkC)2i0?9SbjdhpZEDd+ch@m`r1#%{f?y{Ek2#5|Ebr1-"
    "!}FAjdg0DEdoK?CkM-8yN$gPQ}1y~@b=_vqoekwoNKkn9_DXvTcnLfT-zD7+w{;@)#iHJrgKb7aaH2~mJO7mzlU4-"
    "zm_Sflg;(uEV8-"
    "I!P<1==FQel6ex`09S)tm(Q^U~h^k>*jZL^YI$B(%{wxT8tTI^Dc~e)b>cuQpdLP^AZSQ={4fXb+J8!AizkETP>b(*_!M1w!^f#3"
    "W-Xj!Zuue6S8I)1L&E%A%BU(C|gou$D<~XH-Nf3k7L=}n3G&|5*)=(KVAyi1>dERfin+OjbRP5fKAT>1_0WnX5G)8(NbPy~PX*Ab"
    "fdd(twM3cxc#hHT<tT2$1wV)-"
    "P^>09`Mo_}eW8ir&tOU8wc@kC`=Rtl`ZnEVjIAwCO8icN;!gI$0sB$I9o33j<W1hJ8i+}w}GVU<xJR=mEDxm*Dhz!WWYDqD=SzsW"
    "?Lk4=F@K&Oh%%jmy4l?o>G30;nN^&&A(%f2jThNdsL1PM=sNz0Sk}Z?UQ5y(4hD09#Mxfo56(&luy^`<tV*V}TH_Lbgo@z|rRHxT"
    "na`Wn8_tE*awjZVWUL*1y{P<h3o`7-R#!v62m<|F4bKFo<^}pzEG+)JKyRP@=fyL^r1cO?N3<K2m*VxwHdA}&I00BcM-"
    "`59I&}WU;cilw2rpqg3zZkuU8Umh!_8+wMO6A|;OV_m)d2;O0UU#(&6-@CE&s{1v`0DQ{V-Id-UuPGyU%&O^+@4lK@qlwtu5VLS9"
    "55-"
    "H!7>QYbd`RejJnst09_9QRndDUL$f(Z_Rv|ROu`p;^=ld(h~A$VDm$}^9_tn@2UK+{y+%SPTkt)Wn&L3Lt+xeQCxxErPt6<uU8tf"
    "o*EPPs1Niz&x`z8<61)Dc{pBpCivy6R)5|WkL7}^*`G8VVHS^s-"
    "PrLec)DR7e^hgD0W73~C2YKzPPS=I&#aZ(jeq5677C0%@AM(pEoUc*$V2W|Ce*~f!Z;Ncp6T_lDf0`K9^Kn^X@a)Gk(OJI2HAtb2"
    "K(FPf42WARB<?Q@v<4yCsbsv+l8c-J2_$8rEQsMieUe;8r@497hC27I8~O(bu1GdkKrut4mcT3nrN_isLV3c1;5G;#k02bH{=-"
    "ePOg3N&Ex|F%RdPN>sz440D1v2)VRH}~V+8e{y^TC^9~4^V=g6#srm<F0&WRy0l|)%0OW+_VV@Og<&sdI75zSpjj|fSOW0atszYS"
    "Vj02>X`oCq0ZaL(d!0!$PnQjCD4yidXycuDXBqnKdCBnAIg3b-"
    "hHiaE(FSIiI*xlX`j#OtlKyPwT&u#<fqYui7ysIPzjTsG&cG2fYc^bc8AZq9ehVIv5;5VIq3Tx){PuA$l+e_d_=^=(I5-"
    "+(T7<R0YuF1Gw*?e(aNy^k@i2*A)c%~Du<a}K3_v6n_UKhp2dMUO9bh!tD%4~K%av@Y^$*_4Chb}}B0W#FM6UrNbaiSSRS$EU|Xo"
    "SdDX9*qodpzBP1tM9uBfWlhWGtcQPY5Es&X~a4k9?jMn+6YC=BVqye?PgNyRD9ol#{)cFyQ}#{xd5)69l#R~dQ%L50KNqH79M&t3"
    "$u&bOCVmtBw3PWm${^|^yv@vdmup1=eaNc>wevt@01cvs%HZ$e4Aje>H5)7>&yFV{lyXWc%pyt**mKL@eN)K1}rQ1qw~P15RVQ9D"
    "^2*RQ(AkeNywCXpJU*`dK$8h+!&^v)SxKg&j~(7HOaGbQKw)q#|3-"
    "VCj9rU+v``FI_IMU)vc_QpuY`B@vKQyA}d34&Kli}4LTF6tbh+hRA?9Dn3KMwVWTGb!~qJJAX<WA&n64cF&+^#hWE^17^V#JJ2@L"
    "A&CzP506{3+(iJ`tPGB4)ml<VNI^2_&R0<0f$<}%W=wr~YfP%C)mIQ-go>b;B2^urOo)Wz!B4eQ}7tru2<MuuG@UpyyT5{!d&^7}"
    "z0P8416N^EW^tzG?jsDAmCdFs~pwaMB9rA(#NCCFuK@mk<&<@+r2qEEB^Q0m?(}$E*P(H-%4+hq*u|2}TJ)?Sx=uCp*6!UO4hL~-"
    "f3bgioXcAeo=<gp>mdl4boJdr<Vu`UZVH~*FJTk@H&xv5jG_C)@@Z-lgYuLegV5m!gT$Z^W7h|MRdW^3a=&}-"
    "d`^K5&P>4+P^U?d0cSq;P@8I^6pN>vGyg&J{0dT6t?peXj){X=V^s*9{N6r8pXBRTQbWmViAfY-i_DT@PYA_xQ{pj1Xi_!VQ9Uy3"
    ">SwD>U+H8Lt8d~Fr@boye7tU$tp#B+0)rY$Cjf}uGc(J|Omsi)-^PnqfKPkrI6t~9lU~u4zU1rjDnMIT-"
    "o(MCX0EW~e?oTaG<2bN-"
    "4`@ejd4X;OtLpwF<nokG1<TjcHue%VDpBK5>w2y=0i7DrwKj_kT9wD(DB+lXKpJU`BGQm(BB*O8NsQ0>RO8-"
    "td;N+<mV}pr0aRdOY05G7EcYc+kP5*EovaEpX$(@ND3w-"
    "fA2TC>MwFuD&)NrcFlG@G?#bkhvpmvlT~0w*3s{vz*1<wkcuS#Cs9_Sy9BB-xSR}!<8W07_;uHu<9i+xsP7xSED4-"
    "4*;oA&Ff;%Z1G*n0>9+JkB3ZdB6)bQ^^hP}x1pTuAh#HDj9TmNNC=z?GH{be;=wb`n_t5-d@r!|^-je-Be>FXtjHZT6XU|SRZo*n"
    "s6QV(~3S6tLXx)oOpT*GUtA$>6N4Oo}7dc6#Oa%=r698V#K%5cB2*RKu&N*94a)(qWcHu|kL8NIt+6s)UyiUCmx^F}kwmzb9K)h6"
    "GY+I(D7`<2XoH?8@C4DVOe{3(^@lbPYSYfG0mO&QGsBMPmdsi#3uW<4mbBv=rbGZ<sFV6=VBWCmFkbFf}e#a)&*J@33}_pICNSDr"
    "F~!C<Im+M*sbG01F1BEdWOxs}cZ3~cEP^_ccRf;2S7vKS+}p296i&MpV#Wi&PkcvR9fSh(C8=_6w%iWH%YM&*c~z;ld1ou~xM!OM"
    "qKht-DZ260ILQsS^3C_7k+cM=hPQ!iM3O95CZXZh9ZWtJ)MoG#epcpt9)a$qm84}rOZnRsm<UV^+lvXESq-eb9qigFN5e4r<vRxE"
    "-T*kJFyBU;qCcPkt3#@@Tm|JyV1Ue=B7tO((o&Rl!H8<FEziDL&|NSfE#vD&e6h;rxPD#5L%zojnaF|<Gl(pcVnvD-"
    "r7h!z}E_v_Vcj)}QuJ)7;3hi7M&T+7EMPU>)9GW}7B&R#YwEGABt^MpNiiAox2Ms|PA*zZh_rxyDtx}#3)3jAUeVprQI(T45gAKh"
    "|daY1P0p~>8vBqVn_I8)-"
    "JN9P?V7Og`H5o8<VDbWzDm6CeNsRKo&9cVl$*|Scod+)lve#LT3C?KUFStXE<9+YAxN+~Cp14)VT)|2BZQkkOUk|~g!&hyNarUJJ"
    "x6%@dVXekX&NhzaeTyao=EWs@WgQnrqk>FCyNf_dZ_1dwJbpmBtGEQlMHrNEiuxL)AiU#8#8cMjw*p1n+=%9&%aTya=VVuK=$)!l"
    "v4)b4OgcZyq#T_>uD($Sxf>I}V;KXwu1xVW<h=w8rqYU?2OC_xWrOIsZ3M#ToY?BJhFEQv;k)vOx7qMGW=Kq|2ZEYHAy@&Hgah~r"
    "f+t+^y!JBVO+Kk@(S($*~DeSxy^)V&!E>_q}RLEkW^<L7OWk2YSjhk=`%dQ%q;O|>3-"
    "^WP%DP;2kJxtpT)fAWRyRL{%_vHF{Tl?(C1+dx|vYNNzbp91*GF*JoTx)()&ZvvULchmstF~9$W%o=B%A;Xmzyu&TSL-YcV1Dn#H"
    "e8%67_2;$*nViml{OVrb1Kvz4C8gGM`*uHROx=9#(`dk1`oa8p+gh94`(cfx$U;0p|gKGsHW3{^32M@`-}T66`OAO6;%AN-"
    "$iOyk8iJg!>1{3Yafp5)z|v$0+aMYhiw<FgW2^#w>H&Y%fG^eQQUItG}LvV$TBq@^!NnlMl1zRA<Hel2U&ZsW|LmP-"
    "*yOfJ)$?)4&u(Vtu=%ex)*49N_+67`y9Jt%!{=OUsC_40-"
    "L9{4PUZ~H;9v{V`%1!fx*4E+$jqpoiK^P10`x)3~WeD#&{u~P(dW+mU<hFbv`}o9q@bC4Fo8~d{HvN_bjHYfglJaKoLMbnpqii24"
    "aeopi#MZ$`h_MFb!f0zz?Q$N**Xf8!A0oO*=t>j6}e^y<U1EnK9_#3aArA&;eQlJ`9PZpx~A&V=0&u(I^2pVk8h4Q?P6qrU8sh_Q"
    "@m)jmj|<7BLCPCW)LB;S6m6g^RhkuW}-"
    "QkkCFpS(zj{nKG!GVm?p`SjHKq$1==Y8yr+E=ZM*$0EFPCMV7Ik6$vHmqYz9o4jg0x)L2HtNr)^ZA~S=ghPJbuTWAq)fuORXQ3&%"
    "Sl(YsNUKBuW3>@DH3Gz_E<oo-Azk$xJ!aqzJod6ft!sRXjYfi_QwS}4Ztd5Pc!c@G|8e`LfPU<cVIKNMBx?6Dh_Qln1t`E#irz>g"
    "lPh$@bQsxdO;itRO`{`Ene!3OCKPYLfi#`8RQEUH5HOP=vdCOnT4%?Mu*>J&25n4(<;EM)ruF;~Wvh1lKtTyoJdO`*6>n+AF>rnO"
    "nVix|n*s~im@e)4j;#*}d4mX6kAN`{)+%>F_E?nS*Jn63+OA(0d1%aN_xP1Bc)$S1Va!t&awZKzh&@(VJUtE_P5K=Pw$V5_3@eHE"
    "bDHcigG7_H=SuplXiqvP%1O<&NOp*W%A}|am6V!7Cp?lZu^((Cj%}~4q-"
    ")S@v(#b?+LPP^}%u`E@p~UNu0Y)U;!tp2pwj|3Ysgm2)6HAnJ1fIwU^&C*bO3gAS7?#Hv3B&_sjM7BuT`J-2DMLq9DJ<L#am-"
    "L{lqMMDo|3E>BLFSLIt;_l3`s&cmn>Z5jmy9!0C<V3%z*23VsvW+>EagvFqFI^=>q;WyG1$9UgqJ;BM`zag1={(P>1?1J9&eUaXm"
    "Zr9iq~&Ly6WEv^BiAvrlMO(7}ASO-%X)!9R{p-(QB>NcE4y0#)qEg*NP9syM<e!KM;wa%)(4E;O*wn!Rg@C5YL5*|pEQG-uuQ%fa"
    "(sI}7;d9$UUv%?$&!3wbF=e^#YrMM#*Dd3!li?Ay361f=iYar;uXHg_+l10{hi?r2<0FVQQrS4uI^$lC5xBR`2r{L-"
    "C@J1gXuXBfYv{!grrTl4r&M`vfxSys9TbWJrSG$_hJKWdj9(;)hUi|`i{cur_vq#Rc%IYCfdg0y48a4pe1+<-"
    "#UL3_i4PtjuRMoA;%0^=VN4LZ|=kTCC2=Fx+Ww8_9dg|KjA=8Ex-ryd^17<?tER#y5Ts7q)Gq(Kl`C{j+iYY#1@NTQSpk+`-"
    "@Y7T$KjY1C}gTUopdg0NDGAk#f0`aQgiIOSHEsK&#7X^i?QIolZ3c}SOiScZmDMz98HC&*QkI5TsZfTPyKIo_tm038D(C`-"
    "yZv)NlRTf6!K|rkXJW(YSB{8@lJ%)dm!ABLcNZRD!9VldHxKYYy>!UUlp3IGoj77s^u$T%qTS=`?mZ7=_5so1(q3jW@`+4LnV-"
    "_l>5;Pz*Xk;Wuklox1Xkb%}x<t-dVif-bzgAHxkpzWmCJ_RO8k!<Nx6<(1xS$enA_WQ65QYLrkhpy+SWMtrX+>CwUcEp5;pqM3^M"
    "@1cijxnYfBNqD6nf$Dhx5sIM`y>VA`l^#Mn|Z2e{ctiV1P=P>QRxW3G~zHr30;0J>vKupN>AfJNfX#q<UDhv`&uRfBNxgf|ZBGZ<"
    "celP{1!3!Q&y(&q@n({q?j<IoqG|$^DgoyAhU4+_xGxq<Kgz=*h`k(xTV<PH`;xtL3vU6y`14>c{|=Qur3$+4QQ^ynhpm@2hN+f#"
    "CD=bkk}9O0>lA6}te%3UJuokzpqc>3zSrhuheh?*%CC=&exohIyBz^0A4b@1?LB3lb=-"
    "5?v6aBZzt!UkAAEHG$oqBvn<{T>T$x?apv#{@k2T>g4SF<LSv;_~fVKqqEPa$3MXgISeU3sVA}P+3z@(!^JHMM%R}AjVcNjD*dhA"
    "N4|im>E_F;H*y~c(V}fXgnZo&<;Avv<L65T)&X!X_7^0G;RvgH?ZI)^YinaSoL1mfqco}}?v^9UNFH;<Dhs0U<$88iyhtW<m(!|V"
    "&<yS-sw55xECEKBT$~O!Cx#vJ#IE^YH+9tq;)qRKAM5yGeUYChH>|JkBjjFP_x#qJ==qXD_BMl{mkJau$Cx8fED>_%4n;Ll%0`iK"
    ">lTD^paEsM)!Z;Blw+3STaq9*GowjH;y~lW*NO!OQr@{hLHXI3fh-"
    "J^+DIXoHY7?xi7{}qqy(ztz#@UafnrYHf{a$ydSNh*JBy%fp~fMT0QZg&SRivwl~ovC9ke|f=oB5OXa-GeEC!0FG*hS<%oYY(IC1"
    "Ynpd?{7RrGjZ8vZOr^b&P6OIl)!0!}bSTqa%xXaqqbwmOmCCMXe9NP*T?ig-"
    "!^Gco`G^CCcH7|*z|j<;Y68VDiBnCu*PaG6f<>I6+%b4RGto(t|&5DXm}lHfdf<}<*WcjOLH;G50kp*rk^YMfn1Jj;dOej5tc&YG"
    "u)+Mx|kyJs`Hs>|9@rvuzz%Cm($r!Q{T{-S4FGicKCRb>a%3g+GQd~ff+&E?V-Zg<_E{s8q+4&f)QR-"
    "0XSJKM0bPQ$YMw|4;P^QAk1=v`5yOl=U{UbRpXSm5EolR^H-UHG9skzdGZ+sTk^JU=?Gf}S~jJS-Lg*iC_Q4(3<x>-@_Mmj-"
    ";HhxndabL)N}!ESv04SsiXQAwpT)cTjT!?ZF?DQQY88}II#Wz{%9blwxC+}%Iq@jzu2;B}57&;9sfg?QT5Q>0(#sxKaTjGqH6&~p"
    "gJWdN}gRO!L*?&6=&Kd*m>$!0114r5zFF>9xj?!0cP3(1{0XNh;ny?JFxcDfEwdS{daCz}E8BeINm1*BjZwFlK?<hqFW4X{*3UCr"
    "#R%Fb2q>p6`4%XZQ=%ZcV1hJ6(*zgZp1Z5q%iUG-Zz`RFlEf%QrK_UnD7eoB|N2>82hiNKknL7vf^i(&eA#2mdJ%y~5Timi8M?f^"
    "b7!@*+97I-ogTIFK#jN|hFjEH2N;u39Dh$R8Ud$h)?=vd6mD0Bvpnrjg>%{mw$C=--"
    "TQPYS8k&^Mm8Bhb!S*T>37dkl)G~*(NE1?q9nk0yh*-"
    "@{9)=DMfNdPjS*y7e&0*pg=cE%AwB%q0B4iLxDka!AQaz>pcnIs87rkJ8u1SNujq88I2>6DS$QbmF0Br_>d>5Zq!LE)%~$_4auAR"
    "G@cFxY&O3aH2t25s-6#zP16Y>-g2%8@~E<Dd@E^n^yM&@qE}Xg{4DiAhltXckm5YvIip6R-~x3djYQa;*qj6cHO-"
    "3<(43GwLOa(pe#lV_bWqJU}EPz*LDEn;hkpb&;?X9svYOxdFz*{JX*tD7kjj>VPEys0&g?;8hQ=3w}Wq=F82r<mVy)fi^+~p`qd5"
    "TxEr4I25W!82~PTtrpU0U^(b_%1KKFqY+*)yrPule#op|Pwoj!q`C~3i5KcLaaT^NC~G4s-"
    "61P)Z^rtK9sGd8;w{v6dXcWTGHoiPP+MI04a%38rnJ*=IxO}S2g^lUV<FMso8E_0#EN+uA9WbIDz8L^KK`|G0!s*-&>_JD-"
    "s<$CGLfGC(VCUi_isu$pSac5B7Jb#$2mv?dF54g((0g-"
    "RwE0l2GZs)!hmXpirMT`QS<vD%<TA{(~!U(h>UxUj%s;18aJtNR}=DGfo0%bac@*9dkFo2PP6%f@Hs%i2bKF)qsL&_S34vPs5NrE"
    "rIq=5=YwVgrhS1Egu_V<hlLlqIj6GWnzR#5cWzR=R&al>Z?IJ?yXG*y;YEk}Fo2X+`=NzLa6#B&Z{!Yy@Z8-"
    "FHrD#ds9>3^!80a;;JnV5B8mk;LUuU@jmA%gpeeg^0T_WAr3Gl*Xd@%R3((%gdl?l8`!N6_LPcVrAaDyuK(2cwFi@wL!ZJ^3Rzz#"
    "bL1#z!MCh!u0!pBg6H?;2!{qESw7u{NbIzh^mIIn`A|;T;(2|5Rou$q2Yzkl_1m{#5LD94c)UZRtFs|^lh)`wl(85_OQ(%suLotv"
    "J6qqo^yvYGmRvBv@O~6acFllvydm)#Q;-"
    "(Dx8}s2}NwlWci2#*Gr)=wFNP+_HWTiBy_N)YtLV}!6o<%(FfiK|hc)+A+=J4D=B8Ib~89+e>%&u!Kyq^G1u>d<j3W90_C?u&CO6"
    "={R<&o@<76f?x(*^xK`h5BQvb&sKeEWS0#da64enJud7m@IJQEH71LUk4P|JER@T2!H>&X0fk^zpQBt9A0>ZMC+-"
    "xBvU&$%pgF>G9dgyU&BK{?C?&A-"
    "hQTPn`)uaoem{?1ResY@K>9)jh1LIh6bdv)db(4B)q;s<&1S%e|lvFfSUc+ZWScr|ov@rU?AK4fPV%qmdk41y*YDvQ6(Q;_HNT^%"
    "|>s)snl~)d%%a=PX^8kGH-1z4dlel7mhvqO>XWdswNwrJC;L?(+}mW(!NCib1wu!{tDDdxhN!v%C6hcNM-Iw6>M24wUMkK2^l2JI"
    "m%D;LRN3ihc6___XL_RLs~IT~b^>y{Qso)yA4Iwa|Tt?4{MJkElR=j~k-"
    "w{ug0he0y<7jK+A;;^p_<sGeOzUpsIiq_1fEHXhl7<Ojo}0@ZhjC{I}L3(<D0s^F8(I<`pg4xCHW+2*QxP9Dl|xgQxm?!%8O#mD;"
    "(caY=53cM&uKCJzd$?`!lUW7CUF&vZ$frDbE7?>xR#3E0iud{Pr1uLWto+S(tl(^?gBqBJ9TadyEwWRV|(I7$4qlJ$#AVrDe@E;y"
    "BTKFr<lQ5pc{{zT*!<4cvf|kraIbEcA%HA^vGTv(nw?f@+(Q?RO03REI@J?%w`D(o-DHj-UUc%!TT*^y8Bd?QJgoA1i%y5w8LP9B"
    "AqLE?zRiVA$*&7w%QCx6~L0>UAP{v>j5%>F<NFr!x49b%8oVk=)N<s#o68y+hqD@jMXQ-"
    "(K2_9G$l2KuxOqvpG3wT4u#z+n5WndA?gpvaD_(I8(HI@Mn;GJ;e-2_JrluKc8NrEOecw~?WjT*PvvxQc09FT>h&jm-"
    "H4Q&CP6jhE02lC&b6N6XKXp#Xh0ZRE|QU=mrxWv55RI`{Yw6DsVTd##NMxn<B<Dl$0u!zxKW}}Ja@ID=<HmS!}_b<`ucx!8<V&hX"
    "C7~e~o*V|EtP4Vhg99CTT-@q?m`rGVg3;Dj`_GN>xr!Md@)vb#w?>2fIXU_3`4`<hh<u-"
    ">~=<{+3zT9!B)n;$5{pIYs2%oa<4+YVE)%XwxDv4F-"
    "rh9m?DCn4Ff*XWOg?PDgq+}jRh;OE(<(m60kk^x%J*)N=pn2H5<UaOQ5}PkG;A@2Ur_<wiCvWjhR`FFo{`9f@<<tA44<BlE-LG<;"
    "a{KJZqjw+wKKc0J{VxlbR2}=xtHv>_yJ{ah+yI)*4tLY)g(zYEyqaH(0tojep_>`}a-"
    "qXxPa3|(HR75tPo~v*3zx#L?9YwSYL%e;;#>1z7??2b3K8R<yJi{*?A57UH}}eWtLWi$H0pK>Qh8H>o>~=es?9#7?}lf+2z^VO)L"
    "Pp>f>lwZ9Ek8#dn1@4foq<X)B)sN2v#!bQ*a@9ZHyHdKC*=J55X(YRk$U}Nb&+SDM_GlWp=14i4>q|WoDp?bx@vA6SP$zyaHjII&"
    "`AtAY(x<N+CG08V%za$}UCGlNKbR0YwOk7xY-vxS7nX4Ls#297t<reA)D6QfG%P3hFY_m;)$R;uYK^Yb%nGAaw;46Ydy<&BAhJ2q"
    "vzATL)}W(6CvfS_hd+oZwzk3vVeJ3`m1X4z#8o?dzS(Xyamaj*NvUthOM1|1AseEeq?5zRrHfGyDrTy<BEDes{$<9I@!77H)2@0a"
    "Cl5P`6*d&aQhNO{>%)4EOn0R2jd4(rh$gKlnOKe4x~@9V*k>`cVhtNA>jRtI`5R4mK*V(WzS*WZa>8yGzTyq-"
    "^B}W)Dh#!27<rx13zJ!c_VYRmcm_kjpf9d8ZpS<ys|Jb{5C>I;-X5xMQW>R%EY-"
    "^vR{C+76d>zdAf+*|A)h26hpp&^i8obo%bF=@W+^PY*wx{QU8Jxkzo_9EQZ4&6`eBS$s}D9ald7XUCt8PN7ra`OxS0=acWCQ@ooj"
    "vmk#I^;`F%MJ4nB#za-|^OGYO7-vU69Z%jL{e5!w|9(C?h2nqwcn-"
    "z>_`i?ec7`NdhOBHXHx~5S<V%@!2UX|>)x4<Q+bd}3*~M>ZnBuGGQ@mBt+nrMH=D~ib{cV)?m)Q(Y2-"
    "|xV;oM7AHmS3~4Cg2qEHIF|uG={p)stI2$U09l5O3+?qF(G~SK;Dzj-"
    "~B+m(0@zRH2+rmM36OI6wXT_WU!RK{k<=CTE{NefoF`Zw344U{;^Fi(gUAf4Kx`_*xkyrR65@d`q#v&GfNn@xRSp#A+DWT;S&g2b"
    "*jAaImoP*)IYffEqXm?W`~vEXzJg&M{;@VL%9(WhuD=O>Rvfo@Xmf1Wj%N3x=bZM!RV*6li_HH16*L1Y{O4Vvq_MWPPxiI?rR2&M"
    "<%m&I3yz{i%zD1R`BP>+Jx5LI5=~F)^ZBEfquoSxAv3i&{AbaD#U8ky2}Aj+AQ)z``_zTN&JzCNM)#nWeTeIB3jdb5Kr8%`K3EVu"
    "?TlMhEqTFTBuHqqVmZzzM)k32(urf#-"
    "V<T;#Zd>M1I<3P?%}ZWMF!MhBzddf`Qs$Vd?b6gdfZvTlE_x$Qw8PKF?|r?Yt%mHA1HN*;M<xt-wOygK>t_Tz`Q??0cN{Cxas4NR"
    "1!0v~!=J8wZzeskAThefDrUWKgzN%$Mive0JN5l_A<SL3^cui0L;-!Y=iI{0Y4;JPF^-"
    "PL0g(=X7qW;u^}X6sbF_o?Zo&^JA2(%!Ok+~2ahbpLEFnE58JDJ)Vx-ITq$3OMh*9bPYk<JAwNcy0|W)gk>x4Kitj%aZ`kIt{iVX"
    "3p}nl@@xJ0?tzs_gdsZRW)g%nn7ze!OZ@Ca{lAT&uFLyIP<nxxJ>ZfegE<O$;Sy`%TJRw`q|INr)SuwW?yfnm(%~Q=AK{E3>N@gr"
    "GaUV&p%Fn1{nBw+TQu>?a})q`0Me>4?mutbw5wnog#r>eRn*mA?dqcmXJ{UqtR5l0_8C9<MQcGGP4Txx~|*?E<LQfazBbuy<koJZ"
    "A9s`LnR)N6ZeoqU}1c(oF!Tmaa)Y9$?sp#5NKK5E1#KpOM)O`tK7{kw~c4mb;#x}Q}a$rZ*PR}su)XnWCIVX;wD{s=pj|gh_9{|1"
    "UQ42@=gIK>eSYiCqe00WoGvOw;Jv9mgUL}T^*%VHU2I2C-"
    "d!*?DebP)AZLb*v`c_Vw9G2NNj9NV%usy+%vLmwaK@d*|sS1^MbZ5>icliw)x>N!`%ST!)i~xMk5`}-"
    "<$|lk|odJiPoFMxJXIcM4UF<=?t909ZfV_!)TQf46~-8{f-"
    "MXMrBBF(kGpbP{4bDT^!>$1xGocnAbM?z?q7fhQO6V^5Yr}bf6Sy?c`~eBt&f(!F&WjgkCusJn_t9yipz%5e6faG7f(N5)>s5wNA"
    "!h76THbklYK25v3>tYBM>ZzX4%c7@E;-"
    "*~owfMw;<JJyDdRH4$glnP^mw1Zv6wP&v=k`zSDu6hNrOza}M}W6W43lLX)kJ`k3aarQB>tz^7{3A60MT_m*FO#kM&wLG^M4r^b?"
    ";WlxAR-sqVwQx!FijKLOhxLB2l)LVd{&~kLZXM2N3;3#{!%yl>UlbuQNKkURd^5^qbwB<ZENK-QHeSKI6BypGy-V%Kh!@vyWYTG-"
    "XGdV$h6Wm<*do|3WwEE-U-"
    "%ae>_4WLx0gkY!hAQoEE2QKd5xz+8UNF(a#?w~p$<3+55%dnCt_K5WfcUeWG^rGgm+S&0Xi7gf{hs1hNrI7b1lDLy%EH!@g<{~u6"
    "+5s!;}M6bk>rCV4kpp&rybAXor^7pwGMmopJip$p@g7led$a5CLGmKl#Vx_#bb7Jo@m%@#JSZz{2i{b*a0rrt^z3Q0tIFtp6SKRU"
    "j$&#jwcT1)IvfiY2eBDACi)g!;a6j3_T>D9G=El}k{r<;&i}+T4F<e(W}9I;bD|eOG>N-"
    "O64O6lS?o_u$IzU3_id8oV#Xs1O^dbJ^Tj&uTGc7~~i*q1pp&_dO?{fa7jv?Pf&DNCW+U>QjAacaa=I8uoyycNCL3nCYhhKEA!`Z"
    "&IyhOlbAu??1Urm$U081&9B3Q*sDWp@rcJGYu9P?E-"
    "T^;ckne!nntbm=x20ENn2~hkaP>I&{R<2`2^gl`p}z=9BU8ZB<wse6TJxj-y^%SJsVP-"
    ")?aBc8=w)#LG_bS~E)7im6*rwx8lnVWuqNrfOUm%2kHMWdpjIp`=!t;@<TRWK8!!#t#t7>puI;cVp$}7R&4IE$}q-"
    "JdWb^B1|VW2J8a-"
    "G#E(B;;EucUeinnPm!AxvNwbhYZ8^h7))TIQ~)Xs0<J@6ci?94G61nO(mS6O_a?AR2{pnQ0@ND?=R9e+Ap=U)R7X5gMV}nYGy<&B"
    "#L{GaPSgb=BlAjHAaRUVY=c#SYJmO7FuAv*givlcHyMLu0n3|`!UT;TZ3@n2W`f3)ElPNpZlO@g%FJmb6y0<j3mRS>JWg`7!1R&E"
    "P{Ln%nSu3nwvxHTxhCFF#x0>VnhdNhMTo?Ukb$G&DMBQSTuhW<IaulV_9?=*z~nBfVH4xBo9-"
    "}17B^yWRUL)oE8Hv;m$o+fcpICzNyUry-IGBQa_F{g8uC|b82!1y_f}lJZ+vd^oUGwzc*C=+;v4ZD=%j;XXpCrDLN4{boZn`cU#I"
    "Bc(}uX2mk4uK9ky#WCM`>c)#87E>&8L%!ZvgGz7V_L3@aJCQ#j}Z(JVA2(LG{gmkzDo;qNU^U%q{v!8dc@-"
    "J<B%)A{Ura3H#$Q_x;%7B&m+j^ijXD}Uv76YcpBcqcA5$HZC#!8`HxV{R(_iK%-"
    "KDo}~PDvQJKpoKB*C`j$<u^X|wW#3`Uv%el`_cF?iXS|9);eEku_HB`o`v$mO2KQ8{mm#$m8~bS)P=Ms^VQ%v}yQADD`Wh4^Um(v"
    "7BoOH1)hsS{VewJaxTg5MbqQDT31dx{#sW?M!2Cp2pcwoNhv{VDjCmM1ZdUoOhTH1`>Q!>)FSGg0PTagb1y?Dlu5dwaR3zrE=nRE"
    "RHD<ZIDV(!!;Q#nVXFE3X@*}&$^719+;rMv@F~C+xysW6tmV%en^HIQe$%9`6>w1j+Y_!K*?=E?X7OfPx6+nQHgmEUA;ErejQEq~"
    "F!FU>Dw#*td<3-"
    "kWS|($Y^qxq{JWEDPxJ*b1lT}m%y#=lCgjphJu<&~WtQr7e0Ura$mm9ODmJ^|vkeO&6Xw+IV<sygsLMz}wv_cm_sg##7N?={YVQ3"
    "XCsyNLd!rd}F#HMUwfX70)og&6YBP6qc*}*AK(N5WrsL<Y*!@VTjS7!{hmo1c+5F4P$2>^Ty(V$H*FgD;mb5bY*{7)%`ih8T0r`l"
    "j#@4!fs6g7a#7`WR<2{*{V<Q53r)9ksYMhW0zKw@X4!OOUEmdWf1d`GC}PABsKr_O^Fb6W?*1_N*BDc@d{$#Uqmx3|2QZJ4t+uj>"
    "7MV1}df)+7uUnWG;7AkNO)WTK}>AKrcZsd3YJm?+aD5%%i^fK<K0xE@X|@nXEgX?Bn6nuQniB{W2-{>M+}CqJG1=ke(TjR`-"
    "Wwe3(mi@y8(?uTP^T3M8q)h7czUnvz_IB>(HyW}g*;P8FDwwL%3<$}HJ6ci0~xHR(JYJBR@rtK~L;CU;LH_O9TP|&h_-"
    "V6R0YPK5tyFQQHUmeEm!20zud*!S7B)GpQ1nx-sd3JmK%t61ule3xh+ita#@weOfV(hRQjCIuUR?OB(j@nRvqm8e6!)#yMU;o;k$"
    "yajf3Xolar|9I4>Bt82X*mI#|9`jW4Ge=2)23lJrn~~(9pDxE=jSE1#EU~^3C2Ek^pswf0z7yuyP&AE%Vc~FrKo*b>NxsiY`mFPY"
    ">MW@b%>zyI2g5;2{8>jB@Vjccs)e*qjx_a!Nf2*|JWH+_jvvE<7fDwIhyZ>8Lvi8la94>`CORby2^E1?l}DG=ql~;@ARhc$hmF{s"
    "_Z<qS5_N9qy48!uiVxPeMf!6?gkwVvyt>J=+0jIS8=X!AF8`*`EFMW;AD6;R0AJe;^{80Pf2|OKUwnhW=LQeu%w%A)?AObWCMUz_"
    "Fe$npDG`PVEYf;6=A#Iz66FHmi93rwte!8pjeYBGX{uDa^krI^kd0WP9+hMiU5$usB=*(z(W$H3?W1Tg;q%eWLiumn<;>=vspU_N"
    "UW{2HgkyylU&Hc2q0ieh-Xp&yvcx(bWEVYmWeRWBMQwV6d;`P(FLfii6Ss$M+eLpr4tms$To!}g#>!03Q(9Qf>F@{s7+yMAV(l+V"
    "c=N+(wb>#E{RstQDh)e69BClQBE>xtfBz8LKzOk9R$mo;VrBTG!vRka>Qz%v}ZJ9AV?zwb4j_338$!&i7QGo<ABS`TdxAVAhJUYM"
    "Es@>4$w-*lkeAh-"
    "AvvdefaPZ;qLhOKg)XZ@xu?mHD@Q-$ND@od4KfX@%zcyFF*Zse13ZJwvB9XHUap9|4%-CcXoXGGsw>Rf$+Fv+*n3utnZIb-hakW3"
    "!mYxN2hOp1pb;FolTBE`~bH&KE=)Freig$bv01`C}HeEnXqxK82iI4BjbcQ5-"
    "+Az64So|A8!S_72wRjT~@|r<A&S|S2n(Rhn?Ep!IyS{8G9Jl`)<iYwli=Y-"
    "t>N)xm`_H!e^!MuHk#s_5fv781RZeuZkRQ{jPco=j}W_Kltp%#-"
    "Hq*xt8HwC)@!%d;1wn8T6?)R@P$W%+H}|>$E`^Hzl`SC3S8l8AJ@miouS&Fp2CElc-"
    "0B1zrw&@Y3}z1hwDXsvO$S2n~CUkMl?QTQL_%*Tww?yKEcb3uO271}2c)tyPm{E7>seSKAaFB6f>W1%N<@81ATP>7NIT*j5@P<k9"
    "KLS#{;ecDsK(xXSyqo~?jlVOqGJY_NcC6(aP5i5r*!kEXf>bI<Epk;`zi+10P`q-NTk^vu5&3c2LT<vwp-ef<9W(g1yb|KbsT^8L"
    "x%YA!rI{vKMSr$hS1Z5}@#J#>g~W_NsBm}(vl+!l67w?ej20iP|bjcWHOm^OUoivTo9jgrYHL!yt#TIC(h24jc<rYK1hi9~2eFjT"
    "0NDNr=Ag@O?cg|;O%F6EvR&EYRHOO}`?L}SWY&4_b03JJG0KxTqxsHt;FB%LY#+fw5T8VR7T<hjfwdjf!zG+<TcJ}D-"
    "$mX^cqJdhnV@N}v~a7KlIF;g95z<`CWprxRhLbOtOO@ffrDFJB5p-"
    "w<rDKSQsi%vu?5+#;v&0~_laglomw=f!7Aw|sr7dZ(Y9b2Uf3~FT2_%~=`Ee2twL}w`|+*LRp7{)rq6kFS$5w?>T4wuO^mRE5G@B"
    "`fiUf}m9rvME<0E@l*r7~gqbaZmM<l}cRUzg3m@mEli;X_hqa8XT;?bj>zgu8Rf@a6XEpOZPRJYP$gi}V%qwyME3u+qUoQ0d*uc&"
    "9wJXWp^);&$u$)f*wn@ZOcws@8LOEKJOGfIh@h7+~+v`0M-"
    "xrtt4i&VB@F{RL#_+0s}brO|pT#=2y)+hJ#aiSI`)!dFuz&3gOe=MVpJHu?BHtRu%uO9hM2@zGC{Pf&FH7#E;2UyhE1R~`UA1m^D"
    "j<hE9e1wL^Xdpq{uyL&ReB22B-"
    "l;h+>0hP|U4P;Y)_x!0~`96NnTW~S%XjQguz4NF|rmEZU_TE|gPTtW7(ybHP#kYad?91B0+bxsyWjUysT~}wj?rO3%0<{rSaA5Q!"
    "ru1lhpWr<dVt+Q|UZ(H2^{-yN)3b@dAA7f{XW-pdxOa-X%-p-"
    "bwvy+>?hRBPc2K$2A$SAOkNiek!{WVh{&2?V0d&0we*Po;ck=fA(b?IgQu6;eIsXO5)%n{WyUp!tH@&O!UbYZ$^vtd=C)e1WE^%n"
    "z%x06{ll$kyRS|>BtOh@?O7AXuGgp6KaP6i-nPl3&*6UW3nH~>yJ+C`EUG+QG_)S!1*-"
    "ejn+C7STA#g*B@!q`Re#N+582hZ=T$mS2=Cv!u(#?QZd*5@Yw?9%RSh}-@?~Z@@2z{?UZ-6%WaE4wGASl}-nOBVg_A2p>!-"
    "^9;j=RhLhTeUDW4n3%;Wj<C+pgbgCuEzdJlpM&ZQ9{c_Dr@YNN*$M^<UFW{q?^s8=jpnIz~^k3`19QXOrbN8=}0VUPS@V=f=3iHP"
    "Jp>DWWA2{v6O0zy!Fuq^TrYV?;PFGj1y}nVn8pDHaV0J|r4~X2NsK5YIF`(Hp26rC3Q@jO&?IRPn5+Q&LiG1N9UWz^hC-Aw;5IJN"
    "1l7D3s$2x80(n31)nm1&wH5p_6eU!gF+%l5mo>c3PyY7%`l4V`E5$D`|+9n7^Gl&lH+P1Zm*jSP|z0vC!Pwg^-"
    "!oOhVn6@?2_~Bn^&Xd^q@=ngsvY1b>o|%OnWlJoEiH8axL>k!Q67_-"
    "Ee2d$?V<zt#rZuKQsRw&At4Cqmh>I4oUr)23G?_;G3|Ti*u=U6>;hE=il=eos*dwyNxwF$vt)uf<b!rEfw{iWb7$+D4?Nam1v)?f"
    "c$#tF{o!e}yfqo#GU1v*WaMN2~7c&u~llAve7CxNo)GvHq!dto9QXec&};Wp}!~o!>NvEHJV6lTEereL-TMatTm&^=;8m;eq#(7G"
    "{f8+dWM^#<OHSPZYh?JKHOvhlXY<O9t+vZpGZ&h-"
    "A~u^SIk9J3F?oFaC?#QhDTEgtbL@5m>DSJWiIBQ2?k!PzwZy5SFx6z*|;XOC9%CL)j=WS2A8}lAy?(T9%4epYcR^z+%m;M7|a@J3"
    "u_1gHJ&?7I=c6P%52Pm}*L-"
    "z(U~BW(F7GExZ6OWSmlym0?L@DqC*hdddV~aj?NC%sM4Bpr6$enu@#NgrG*75+x20))Ag9_sm%ew_`x)0Ge<uw6o@#Kq&+uuLTlz"
    "QcA$%U{X|4C?6PNwc!BpJkp@GS5SFqdzvEiQOIbO%t{H7i1!9)Sa8co1j0otm?Ypaf^JQty`A|68;bdQNtkkkTl3Y6L<9f7ADx^}"
    ";N4C>9RGcI2m*gO#-C5#e*6Ga;M?;TOjDS0DtzmU<#r*28?Ds=cPFH)^vBI%|4{$1d2NRn?Bt(m4HY%gZ4(g<4>-"
    "4^nQaQT!NR?*Jz`81owfE-DF*7PoK=?Px}6n@jp)cO6a;Af5}I&3TM^FvQ%s?=;0hs8uTX30<-"
    "gPQtb}>`lW@%L7V*n^<5GC(^Zf$Lx4zbUB>MG^)zI}pe87viDh5Yof@ojEVKa-"
    "q*)(8ksr?2B{(AOXd8vEkm3`RFua6A&;Ug>rZ;wA==Y9+8K<VeNo)zBosHFx6_dB}ejwc|5oibfc#uhczuUbQ%*;TIMMNg{_`!fs"
    "7T7#4HhCW*V?~Xqf5>YMe+N=PM)kn$oD*bMJe%{~d8=WQJ+p&17Y2b0m;%*k~TU6vlF~(C^x^FJWrqj#OoVru7_AvcEV+6`XO6L-"
    "D04XlZ$Y}OCFh_lM5^#a#;G~tw5?~L*q*PuA891{R5F}!28KXSFN00{NSf^kd#<-"
    "ROzSa0~Aiy0lIy~94R0b15uz2<cOhlkcc%~Pvqk?&OMAk$K6RnYv2*W)gJY*IH*8onDSSuVRAr9OD;|QrV#^FN80HNV)LoFugjgD"
    "eeEkjunnYsYQP6<?8*49(2xu=9_K@?{BbrQhK=<OYz>$mzq3$-tSJ?l^rWmB*E1kcl8E^YTsCs#lXMW#;Cy9@4(3a-"
    "|~v)ry&3zs(n22<1{Tzy8)IywIlRAl2#+{BXVg%86rEaVxka!j;Cs9n9!>l2;hcdwowZ8e8bT{~<v%f36G)jzFfeE96byYSD!w-"
    "=M)8^3>wVec-`?=RLl>kfN4RCjQT9^GY-i52s-b}JO<<JC{-"
    "?c}ey<KdmN4DVLimE4HZsl%owrzO11C8<<;@wR)G|Lyr!E$!Q(Q~5+!n)2Rg*l=vsp>{gM!p}|{*?n5+u?ft<c$aogt1UiDG^xqr"
    "s`=<-*u386CG=kJrX0j;HYpZOuLs@@qy2_n7appPes_J{t_uf)do?Y7P`CI2wD<-JT$7i#Nd{9A@!|)~c?LFDrCLg=nB`pe-"
    "O+or-gsAM<URcU_~`89yOZ}P=fCum^iE4w*DAFPZ$4P|AWS^7{ecxi-eCEumY(B(9KAiCunFfAHIb999M9`0D^LG`UWogYKozRXm"
    "W0m5)o3a6G`c01)`6L2!dV$~7w*zW2X({DO3hV8%HFhHxpC1hU8w2o?UG&{ctJ<2vh2d#f>`$5Svm9h1-"
    "C#eWUrR1Wk%8C1itMUADnu%Z=pZTFrdQ)jLn8r>wOK($TVq9V_=el|IKF?Fx}t;P}wxs^;kGOE0;li<2ZQS@~F&b82aV>{Vy=Zy*"
    "<S~3&072|GSe9NAEBu%=?dT|6_9U?rfng?iQeVt2t-"
    "S?77XR=W5>EqQuV&GB;QE;lOg8Vpz!X`{*>egPwU2eCa|kf`_D~^TGsWwALx41SKQc=!D6Pi168(06>^2x6xz5Vu2ZpX)GsGj1nP"
    "@rI|BgdGJ*ZA{iqS-fL+XU|bN&2q-@H!NX6Zq)w~giFCRM)EHv)hHw!%lN8F3XlBXKlnfKuDX9Xr+~^E#L7B~oGfr8gf-"
    "4eBA|}HHA(0E`xT4Bgz{x-"
    "q#W>f1ua*f7{L7PbIXhvi5=0LV)<ghtVnuTDa8spy655jFBYYu+&N;%*ux1qSHWE%#q!PZuT+7ruW0(Tj5VuFvDyJJv$$na|<v5M"
    "!=|!si@F(AYe*b<#Cucu?JVnqG)d!;f;Qze72j$+W2j7KzcLCXSeN)YLD^Rw70Sxt7g!Qe2Uq(CE-dY2c`04%UGY|rD^25=m$xkO"
    "A;BRR4`S}A1m!iYZkAFBmMH`G>5~{LQ3*cE+J<RjquI9BN1}Xpa>`Y-L&F*q~fkW><VMQ(`9`CEM_wn?*lk-"
    "|M{q*_$`N`XlKVwK}`V2{Xxx;(?+j7X&>!2t$VSd`u<@#<Azlyc{-%aCu0vt1Kdd9<W_%<Hb^{G?%7C?Cq_<Ip-"
    "``<3JqFeLpJwx}MU8u_uM(aM;jP|mb1#0d3`WtrL8aubQH0`PAJ%uCNEVlM-Te=F}bsycI9iDINK)r6GY3Z5mQ}0aefcko1gn9|r"
    "PQ$EWpJl56S?^_CO_$Bq62Q|Hj?Z=#o0Yg&FxdjuUVnv&6ayqz(TJ<3z)Jby_|@7ihP~}5EOW>H_twHfXz%{k0W72K8eC60Fu<=9"
    "Xr2JGr>nCw<Fq%J*s4hqXNfAYLp}O?@4h~WE~kzc4(F8Gy0+@U^IdlsiV@9K9e2FhTsQ&=iB?<KI+L+*!S(s{<OqFXsxYstej(in"
    "|JnAN7k#ZXDoxqJtsSZRvd)z=c${KOr1@4m^zDrM^Vh(JwFK*~j^bmPVwdenRNCzH_!AnZeK<cVr{pK^%I|Aifq2_wvb#)|K3&hh"
    "Ouv@n{chu<YWyb2^_MCuWKSl^)f*^x%ig@(B);d3kKOj~@3sZ<y#1tiX@RHN71_~4`l+@@I@{xyurU&(NC`JU@C-"
    "Uh%B_%$2%j7glqZ8b4U#e_pfnnDNVAAJmlJMrSjo``RSEc;rIrc&Cq^i(wVFzfX`Hpt!Ek1T_b$R!P=#Wxs{}_sRb$GwvQU;w#=Q"
    "42F-lzuTI(nhTKj4|z0WonGzLh98qg?_CQYdhk(o@RLYH3QgONr?qk_#QnZRVUnbXYR14a#|(-"
    "JB{dwcXjrcf}QNl=b4CY{hF7G8vU8|tz&RC%Htu|{ei6xCL`M1!W*C3tlynwWJW)N^j3Y*0ICALHzP$By@xq4}yj51eg!UE|jhd<"
    "$RBrX?DpF01On^a^{x?D|{JC9UYG!v;EsfKf^O&e?M*c<&df7pu4utkI#eR>PIF9Bgd0w(#?XBc>uO+heFTQ2jgbX&=y`dspoV_x"
    "j>MW#Y3hr|4&1-K)--);CePH-"
    "pztT(ijkDf~OviJHyMotrm~);e@P>b}#z_T_82j!5t1X!+bcDu*3+VI!@^yn3FAoqaK;<1IUA2vZY(4IS%CMKdidb-UGgoLke;JY"
    "Bl0n`xNu?-06in(X;YHgj{q#u6Lq!qvQm=+jQp^{m$0NvV<!4>k!KoUU8xdUOuV_P|9C=-"
    "{~R=IY&8=()N!ZddE4;h(L8Bt0hij6}hUV4lc;W@Iod1C(ekjL}Y0?!3%~h2TTZIa%!)1NzZA*hsi@Iz?&)&mL8=fZ`KIc(7En2-"
    "IY>w@Cm5I87p<aF=L_gkNRiDKL*iCr{=m5J^g^q#2IMNTEvTpcD+E1t(~|Y-"
    "38qJ4?K9Dq5X|)5fz%;9tNeF_1vBB_&$2WrkY|jfA0rymC>gtb`Oi2>5}+OvlPYnK&_)Ca<YMzA|{0oit(-"
    "7gAahjRmr!R7e0B5sXPXO2-"
    "36JcmCi9%9Uj>wxuPG!tkt0SuMZ6EM%pE;l?s9ld#Y5HtiK%ED}zZ3ggjDFvPxgZCtfQ`|dlp{J!Np?C0Ltfx>>cqx$wW{QP){{h"
    "YFw-"
    "6TluBcVZ$@#6He{~_XO16@b%LMFmbtUZ}tzLk~wpaCfd(qE(fs_3&Z{L^nT9tZgwq}q2adLKE+<K1B&X2x(kMWY;^<zplk+XYu-"
    "F6rLk(sgQPtpZ{J8bQ_wl#z9huW>21bbLkj06vRUG-q;QxEEUtv-MnjkG=R<c8|60m@EmHe}f!i<qmrpUktt$@Yeo`z?mI-"
    "U1n~@cg1Of?PW8YX99<>)=NIgC6MKC&zIoTI;dcQ(O3>wr{r`?m6>jU5AZcxa&@5J3?&1v!~sjXn*EW(6fqNa3`nP84%r<S*XHi7"
    "mQ2G==4QoGREOHg0)pE)_gK_v8~;On|Z%~Xg5Q1w@K9oCBzW0X?50_r&kq?EjY}M@)9rEP-"
    "+0U@1c89hl?7{UUlx`RTI|I`El&x+b)4aR^@wO)y0wfh{U?McX>B%9arMz(CfGbo`zw^+Wi@k>^f=kBCu8f%tp+=%{Y@TM*{3fwb"
    "9C`n0>Hba7Qu)T68q(7@Y?mq+Dfg&<vRu>tbsn5G~h=<V2hhfvXghl@xI@IjDgrL||MV0#!03c^lC3SqYO29-"
    "{HUBUBuo1(0gBq!}KN98VH$oKs<KhU`o%qe{5yOwBpr0J#A%;T9wcN`rG41PFj!(#SFYFtjBgn|Dmem?gA1^)fjq4$yVR<^@1j#1"
    "=DY2UP83GEOP3q{{dMcsYRSges~?Fxf>zr8Pt<14Z^Za1WG=ftWNSPk^=C^}oJ1Y%lpJ4hNXir=dyvQ!jbAT1>AmUA1X>70bRV&N"
    "SCk^o$9xW;G#dN=S#!Fr>0*>F={vu?U}C4A|lk_2A&YYX+uz*`7~oBltapO4_c&+}*WyEhM&m{`Ho>+uqD^!*d@7Id^c%tz`hR(("
    "<UYaklZavKDWhmb~a46&C5&?>pBZCa-"
    "^Y*8ol(F6|vKM_T3%XxaX>ez`9XE&HOlpXPkMOYeqll4Vr+{5Ejbhk!!2h+dS^fqUeAXtWp9=@@$3=hB7yZofO9hdv5%PA}2w6<e"
    "j=)2;S#Kb?O3{^b2}n;>af%=Mv{QwcISx@GY@@b#%`sK95QaQGI-)3!GE&e9C)GQ9nIa27M`y2BLf-"
    "a&x*#(j7`tG3S2wzV>9FLTweXyIKQ+csS@HN0B|unW`caC_mdCtqe45!!XPbK8CzqPj1RBi}l_`R@sef=~)*jT}B&Y)2-"
    "$v#U`s;6X*|f>su~zt0A#keUg+enn-D!E()Urk-@3+2d)lH-?M-ZT(W4p7i;{3C`mf&g%P<e=O}jRXj@UK$V-"
    "&<o)pvm?{drjnA6ibVtM9A>@lYLjHz1^nodV!;bRyn7_6f&ztktw!!0p{#t^$Kj}Bg{T>GNU!qqtf%_6|xK*?yZ#FKFY>NL*ASA1"
    "#lnPNxKpZ8awG!Ay37svoK*tK>RYibpW@%2r86J`Vtk+EIq(cTm&khstWF18ioC+cY5R^%Zc~2ueFrnxW+<PY&;5htB!@sx{HUtX"
    "XuA+94Qz!vRHabG#$w>s7F~K(6QmE``ImmXv?ZF6<6WkYm5%GxHSf`VU(XyzN&rnD_swO%xZgS+&s7M^=Dj@NjOq7;Z3#*{OhB_z"
    "U{~R|cv=zYo80t%Ap}7-"
    "@=LF4@ZIB9XZE4tn_%A@|z*Y2bl#o}iAAAR3jkEH@ZUtbt*|I79Wi}0ita$Yumo7HFm1flzLifAkJzEv~YYBnB_B?yZmn)8+_rJ?"
    "foh(Dk-^`$;dUFA>42{17)x<f;nP7>rWTCe+0aJqWB*R!FEJ<f9I`JpWM+Ku4FSPWzoIvm33A`2W4`O-"
    "tuUns7W8DtILv01z$yIpuZa}>aFbvDpL;43!k-VT??!@)whkr7vzpE$kTK3+`HTc=@tf6;sH-"
    ")d7m7mRa!4jX|eWO0~*D6~Jbk)i$`a!n=+O})lD=qwUALg&JDED*F{l_t8p?mxB^M~`})5%XC-yKg*k3PHuy8Q0=Jv37>L2LI4dQ"
    "Psbz!{)37I4xOpW<ISx*fU`w~J;2(aYBVowo<z79}>ywn_9}Ehb04xTrfSqE4CGrdK7z{td=kY-CUWh`%~(=*LtnJ-"
    "?M)IM?F1x~(a<ZIMBDVx>1d;ATK`<Aq*DORt*GZvX%GuC%$0<jDRNgg)7^gtv~aOY?~%Vl>>9L@r5<z20yj>Xc}c1cRhTBRl55Z)"
    "SI+y8$%r1_{a>#YiO3N1d7PW#w^K1a}viBr7n}0iS5VzjiS)X>$;r+8iD|OnB9^g>9`6&nt9zwNZI$yF~Zl#Je?6Jg>Oo$VBFn4?"
    "2^YCy@n^A0krVKn|!mNDg#x&nUM9tMHo4x)36o9Za;&D_^()1fP=UDshsmc0#9UoUu*=$w%*e!lT8QVv?YLXcn*@7=3gW%ME8}no"
    "v#xV3r~{AAo^L;b=nhfuox71k_AI<D@ez3C5$sZ-wR1c;*%J*oq_qNIOS@c238PYc!L%EG8z5g7#5QXwX_ie^tf_V}b^S0+K2%WN"
    "sh{)KS6E@qjXTeAFfgO)S?c>VSdFj*=LX<BUY@1x%q8CYcZ|_tui|{lpvWi&sT^sPtOalsZZcVNvdAesuhHaDFlTWpH-"
    "<(=pZzIr(sL{PyF?$MfM>xExhQdJDL@xqrsvm|ULFucNTI)P9*Qa3wMjaTw2^(A|l^mIhD+k`6XwqBg-"
    "|H_jOl8_8j!LnQ+2Uju@XE2`qkwwHgv63mMqe)#zQ$3raJ3=nMaZus%|!-dR-"
    "d6jBRw|9147I=Pla`N9FPYXo7Ys1azf#>aPuyRqJLl!UXr<>7z8F{(Pq_Zm%%^IQSi;Ob&`(TynCPKWKmaUrP{k6TUQv-"
    "OBtz)&)zfWeDJXk-CTorEcSI%2v4RXpk9ceKAlIAJ%Zf!ZE+lR|*wBrmB{ldd>X}})3{&Iz9BCyAYc{uc!oBT{28CIUo5}ge|JEh"
    "^9KirOPb2j>iGSTG_x_piN2-"
    "kb@+26;X{qcbR@zpLYNE0#mUE7ZQ=Px(ojIn~Ue=oz)D(L}kMqld*Efd%0HQwWliN#i?rYn$Fxt%G%Zn?X@yeTX$^E@*e(&v6-"
    ";}TXhJ|7HMwJ{Y#u^_*|q+zUGRF*+oA?5>7!OZ)7C_sPBv7XgdpXTy|ncGWCQwQ{LO-oa^-"
    "Yt)qcwzaW)wb59=aP(J*+@LKMQJY+G^_-"
    "upM^;YUXV#lNf(()%9uc;)`Wv}5S&F$x#v2{Xa(`is}wk8Sx}BCE(jAk%WGT{7Zu~yVrn^-f+q$`$+1kUz=KUvz}L_R>5U7Pa-Bd"
    ">!3(k&i6DpxWpdgF%p0c+!?+l!m=4w}8M&uu4N58otGU5eXdJhMb+DPU_%O`5U_4EcGLtz@gkfGf_}?o|C8G&$lf)#IC6%O&L2;f"
    "m=PbD-jf5xXAu=*W!3|-?I1;Fc!N9{auY-@!JFSDj8gxENo;X^=6af~@q$Vb0SWItkEHR6cIaDB^-5T;*5^>P1<9#-"
    "`0PZwAJa483I06oTc7FWR@tb1BO_d1UTf;}wJ}{*`IfHefX#fpslT}e<G+Lf1Vqg)=ELq2>h1E@i3z`w<oQYJsBsig&&(f3noPdB"
    "FM*^-`=6jLdqBjvvI{lIbCA1bjbVmsf=J$L}V}`v#q`XHajcw8sjH6I$JJa{#Z?bBtg7&4@YAkqM6J8_3{A$}}I`#Yxvl_J1`j-"
    "3#kLehK!3S7*?ec0^X2i#fgy<xAqZz*ckS|aa6u5^j;i0fg9)K){iD-%YI(0#na-eo!D=SwN?~hZ3zDqB*w#t%uVt;rHe0cROmlT"
    "yLvQE15^YL4x$|q+>@OMKU|9tZ92)X9r(JzM|E)L%g#<g<BCXf$k>?p^4VS(}LrPmSDQRHoG4AMAnf=v&Yp06H>raQ}IHiy+cHZJ"
    "qbr5<2Ok@5cqb3K)TDb+>otAQ?H#T_8r<_I)eh1uw@Mix5_;<A+>^G*r!qi1_q_26Jzvb@_25RXSzpGPK!5;HC0r@%FxmmGMU)|o"
    "L<r<h5s(596n+6ieeyMf?HjG~bo%drtJ@Q)_Kx*2|Y%7=v>8U6?gU?R`h$BR6V&SK98BQo!pW`^^iV@87s@Z!uU;E+Jg2$jx9Cyg"
    "~g9`W2?GA_JAGAD(`_E4EA$1R7BWLzmvqO?F)Ei~IO;DXL*9+*iM9xXvIkR&P4Ph*J=f#s#<LdHUrKnw(vo}`pKbJPUNqKF3DMg&"
    "kzxPWOwm^L&>Cmk1DC@Gb~WDqJrFOpLUO>T^0N(qr=1}KN)&~67m2I)mg#5gOB(?(N8VkRikTetdY{}v2vHD~`hL~C>v%BpmCMLM"
    "JZljMLh^0(r<siTjEDr`%bvlV-~&ic1}vJzzraacXH|9#d!<-Ha{H0yI*Tsq&UxcI)U{LsWVEpT-"
    "%W7@R0%Odm}z5+EjnuIkCnO+L=*hY<35&^9YsRt+n7T63lzP#_X5~G72-jtsU^a?)MFUP(&F(G-"
    "%ru&1QZLRQ>aeTqfYH&41t(=`d!IuEvCp?0eM9t6P)*$wCmC^&jV1s?Ibs6m0fcl!IObib8>;bV#s}W$)ur}_T&;94#QqiMgD=aL"
    "-RUXXd!mq4$RC*NQu_{O+c>d)LiaG2l>eHfnBr=42Neyr9H-"
    "vDF+s0HWfBl&J<SVwxkIEI>7Gz&UH|IR2@$qz3$__bHaTP%3Ioxk^nlwMpH%=rL3xG)gnsyWJOIL3IG_W}1eM?E{#!%!26;KARRy"
    "|H?*%`C@=PAOY=i8r}n0T$`Kb!NSd42El$Y?dS_7t_9H&VFI33Dr!1mVnQByes_CKI7}fWiTShl~(_x*iWgY^IqYCgadN3V-"
    "uVNv#}KG0KRt4)C;tT^BhE!g)(FAu;6{g)SuvP+BoUiHcT3&lLqm?jx6g&Lz+DH*55prOC*sqfnd*?MX;B@gTg3p1=q}GY#Q_8b+"
    "eZgpUZwqriw~9F>%CU?t%pQ!FZ8WNu4T3!|-YS=1O<tqkCGPPm5Qrs#^S0l-@-"
    "Ic^YiKxUct$yz)Nq6A<)_Y!&nqavINKs=%rkw8av&_U%<*VbjsE1%^)&x9o^h2e>sEWl(cBC_CY#(Cn(3K6j3&f$R*j-"
    "MA<!op8FC8Qv74L{$z>#7jrlryX!jqU>4Un-XZdGPd1;nizH_LLnIUzD1Abk_$Z*Z*p-{?RYb1C|H&wo-w-CicXWTV3VaX+#TOSi"
    "z%jOX9G?K&%|*yBCyVhI}E|uMMCFZG^z&Okq&X6j!7NFtSG71(nDd%hZe%a^GI{3S5rFqM>S@f?2E@xx0*!9y|^)Zk>*Dk4<-"
    "F3s$fe_-`wNyT2>|melCWeaqI$Q?1_*zW_EKK8%J%LDW1pvk2ELTe>-mD3^47pb6i?-"
    "f4VS!v6dlnAp|0N5coOdQfHmAM=lLyk`kWO-u?ZQUShjXTQQYf2|hHs?n9Jq5K`hQ*LVeS)ZcpTg>EUJ%4<H@}y-"
    "}yV3B^iMr@S8Fxg=Oa-7O1jq`B8K#CIT4h{2j(M1*r_u8$ymg#GLkVUpw!m@F4cBH=Dx-"
    "L?ngt&cqbvl*Y!E;fFm^JFJ_+vv`k;BH1p3*AKr)+!49EsTybL&t;~M(yd|<#n5(zR$9SkQH>#a(qn52~QWQYb*VY!M12mw%%kXI"
    "6dN8+)hL4UUxy}@)#Hc*lAfL9xrf@Um9PJn3u%uP}e?t_9STj(%yFd!?Ia!Y9-"
    "&H{6jOdFqwhPI33j0lWtZZoB*wSo#4qXpUnKWYap&J#Z?1MRmq2H+zE%Q$gHoye=oMx!#RocD}Tm`)v>c2YY9S8ELBv<#lHA$4)1"
    "(F5+7Tfp-ZlC~}R($i3zb=}aWIM34)obkK*rBc0Hz-SEVU0z=onH?tWve>U)Gh_;YK{Fd`G1X)DvfK~9yr^i{98Vd%z*|5WI6^xh"
    "HEo@r%VID}U_8v#MKF_>S9$E1Aq9>Y`_0FOcUBjiWg0V&HAv1lir4hUPGD{1MX26?PEZ%!Mq8$*WB+K&@}Rd>h<7X9UP!c83Yu#j"
    "_Od;*E4`F^$X2>!CGDk9C;7-TID9B#rW!GGu%PlS2D*VwI7rp1p#}qEA<GsJ5Iv882-"
    "QwN@=<6w5l;#K=@_MP2o{KjoIezfR)v(veZ@*1Q%_QUesVMEb5+RB`aq=wd*fXA9Uq|-"
    "UsNbCZzrO_VQuGmB)YPK#c6&1vb1~8gU~D;o5yE3OX<TNQl1(8|C~5Zh|+n%Gvc$rxkn_Q0f)eHEn0;DYzNw>fzSXM!JmAJ+yj|N"
    "z>O$%i0d`}N27(N!$qEZnUZ8c3sf-BN5_*@CIPnR!7(N@i!51fbx81+<rsw&5)Hv*%q1*f<Ami7xJ07xj^veLnKwdsDw0+n4}<U!"
    "2(!sRD>7{*p72O451YZ)gk{7@YN#<tfD(6+2nBsgIwnaY&sdb1Pu5`i3CDeMG*g%$i%?-"
    ")79@dZ0w>Z`c!TM4Wfar_sY}pv7i}a;V3k!RVHPtftkg6Q!0Li&t;%tVXzVMX9}k~jy%tTH12<xrEQ%9WI6?2p+042;<@4z3x-"
    "8dP#>`^G_B!mPh(-qB*{tb+>KCxCA1yq1`8!7T_O3_2!oc+N(e714+$(Fy9=!S)n%KAD?_W?;_9*Lr{&qV82z(D1xAD$KkO!dr{-"
    "?>h5oMDap0MNVdv8jSGKnHLV>2rZ#$4J`eUa0V9KaN1I|~<XU@nx6t*D=JoK*_LE=bEX)}H6EwJM2`Y?8$2+(oN}$IMQ{UND&n@8"
    "`zeEV<`GJ~P{;YJ8g6PN!H#D@`$^pELHQ41FOxU&ymMCpBddRUcu*@w>s<t7qauwF*ng=93i7=aCf2);=Z4C1aTmq}Do3VVxKA1("
    "}fdrFl{`!F*OOWVsqBZ`%rwL^9eeK<l%L*$ynD5t!NPZE<QiJRN*EI{xr>myCk-"
    "@4wx^LU_3J{YETazme>sYsSF({%V9Ts(^nUl!W;(Ftyjo#|!xU@yGzXo9H;`8hd%y=>Idz1er1|qi0kScujOPM2>d%2p|^#cgC$F"
    "k~+gP=aP#7{*^v>!lj}Dt2J&JM(~tH17O-"
    "Q`wbhGSb12jgraQFmzzAz%(yaOzJco%wo%Ez^aV>X_3AQny;?`~PT5&+g+y`XGf=Y@ZF%U`tFJf4{Rh=`_oJ)QbL0!asrm~<p(Bt"
    ")pNcFzy&RF&@M%7XT&EL@jNsLGWe(@!xedK#bGP;CS)0d3pR!&lLkiy<>|cKj5A#0T-"
    "c+yhj?{Q%20_ko=*JnsMcgPPSPu@YwY#QTTNMSuZF4albgdLYr5$hF(^ez0)brL&8|-QVD|Ys32d*31%mpR7krBLD7>$-"
    "UD=!X<{!iyy!VpqGCd2#BmI;YZ*;djuutce8$I<kKiM)~LsIi8pG2jH^Df-`rcnTO&y)fJX&DsFCEYnskC<WH&;?dm)%jR>#A-"
    "gn~&Ke(=SV*^NOwDlmIh60C;Q;3M>asvTMfCJ*Lus;^u#_p-be;%;4iC~ONqkJnCB}pb&<M<gqNCR?(UdWaUzAct`-"
    "ryPB|U1OxW_}752OCA?AI^r-;S;>{kL7Vr2)Y<AEEulxmz#DgIA227@ZE%nh33rK`YLnYxt`bRx5(>w<-"
    "m%n3RqwO)YdMGn_CCLO=^OcNA1xR9NuL3&}9Fz-VX!V-{NE0z4V?73Xj-4+>iBJ(ZecAa5Y3gIvIT-ppiK%sh$k4`pbU=iU*aBo~"
    "ycz%r&y)Jh8&UHAwFnGm0hTqDbOQ7NMo>SX_1U>c@m3`}%@RdPSeBBl2F4legN0uTNAv8(#$zt2wjX|+YpaEF{tY>>lR-"
    "U5!g7@f+aYU`fn8@qW$^`ujtKkKM$apRiW`1{XzH|k^hh;^M>er5enS0e|##4U|!Yin`R`)V&Aa#&n~;)Vb?<-"
    "OCx^YcEMetV}`&Kefse0%lPe!CxHJBObz`Rq+z(KgS1u_dH$$GwH+cGk{~E%%iTx8ZC5LvH6S^j2j6?O{UG!Zd!+D}--"
    "h6CTtny|M(~=g-@n6}VwlEX-$<@^=w8SOirXOraXD4=2O(i^Ct^4O$HI_3$n6r&m+Pb;IHJ@iOjFBTf5leCoDr@-"
    "~I8kj?S0@64v|6jOJq+R9uXchn;|J^NK=q=t+se7jrXdSNsN{j&icTfs0*m%RG5s%c!yrj2RTJ>ck@JePFso{rgdKDGFcjIFj4Cd"
    "Xp=<n^Ti=0A*vw{lpl?%~+su5j9qvsdIP{LTl5XK#MS)Uzjl9voqY<o74}p3PIw4vv}+m@@Ugesy&CcDw}72LJQ%_zbR}phJ`_vj"
    "8vO3LV*dmtdY&>+Z6~?L#t}LiAt5N4Venc>xXIRC?n8`o0aAP8=Y8g$6-PzaJc)e>^La5Mu$2v%@zR!(Z6z@-"
    "U_ymTpAx7Pqp=`EaMyX7@eDpjqaK&$x`-"
    "G0&n1ihG&`Cq$qoIIMc>gwzUP9~FQRBRYX#$uDhq093e!_jCDjoPc|DdY%ZI%agws$mJLI;~gmE&n+OMQeC6_I?3MzxN!NcxxMDq"
    "`@^%h#~(mhfcm&Nep9E;#~0>L+-U9L4g%2dt^X^1-Pj%txjbpBsMBXnTr?ws$8Q>r-!zerYfbRDxKqU_RhcXLl_&3fJh}O-"
    "9F*;u|Nce0cxn<~UkuLP<L}Fm<R-nJix?3qR%g^d^w4GVQ}M7Wxkqn2YrU;;WS!q-T&E(30+rC~r9Agb<B-"
    "2{4X9Cgp8f?9$<zQAHgyz#6W#@nlofM4D@Bzg-vl#DvtI62O&n|^;ER~dy2G=H`Yf?rDsN0sGLzm0pwP?(<D(-"
    "1rEaFF56S~e7t$rdTt+NhZKx*12={8v3n~RLr+bsW2*0rYcscZo<<Q4<c!5p`hes!;6;RyRre27~+#$kZf~<e#juHXb4xV8ZgPBL"
    "#m4)w0>4q2O1|kq3u$0i`UJacxR$J$&a!#SIA){Pis1XlIYvx?wCTQciQ-N6?O%%yyiGx-"
    "{uRVzd3VeKdwpP5QPN2vPbunnrwq9_PGAfhtI%vzdXGs_s{**+9Srdh~hFFofRyxR-V5-"
    "v8!z&wm^#aTs5i)NGx5B_5&ZQGHOH@INBd1!?OmG4ES5lr)8@bI4ON1wv#Z2qT7Zfltrpuel$=ArlsAiaWJUSSc2+G?BOly&xmrS"
    "CUA=AkVCWNqpNRly@s9=FBsZ<Iruh|rwm5+ie?;d6cJR}>9cRot(4W~{;;uJK5amk?TQAtC+a|}kqVFA&^1Hv8>B485OM2OBOkVE"
    "Na!ltOmq@id`CMVT?#~NwHV-!T@=+ZM^6wV-ljyS{?NN1K@tlNcEy+(4vwqvf*^~As6`z`SOSq{IR7Uj1?!a4AM2Dz_~%>fSGj?e"
    ";FwW%^F&qEwl{;$<B`nn^#9I1~7W{q7kE^fIDux~RYs{;4hV=;$@McT#OF}D-"
    "YUKAK=yk!P_A2qT&j&;)hK<_%Da}fgXn#b)kc1Dxg-"
    "M9=vrCsu}SN~g;ZC#47$Jyok#f`7F_PL#bK4lA6L^s>);_6+E(ZDP*gR{ZWaCTr8V6x>I#<kuYLzOCGc4=4bF0gLbC~B^8VJ-MHr"
    "}aDYyxj&&EfU=0z1IJgZ)~dF4ba<W59~4C!+hYGA&COJ1X-zEv<Xli&!W$O;p&8${%ABTW|nXwRER94jC-"
    "O;&^y9=7v&0hUoMd2@%lK*75K)`?_%)&^aM`>tC>3f@TQo^1u$@9pi!HO#))AY0hH8*C=A9?3gdj{oH7!LxECq%L~Q0PmJyTQbIm"
    "joTpm@Xymdiv$E$~8;BMZz!Cy`f3y;2{kmAXQ!SLPT+u;c;!*_?L!;9m07sL1O21N<UxgHBedCa`V$5(rI{pEI8q!PKp<-"
    "!gO$&;7QTy!`3I#w?l>oU%PzhghyrbB72+Hmq83mLDI<-FU)*fE}6BY}DD>wuWE$`V(MdhgageC}NXqAeCeuU5cy4wD~xH>2L^7-"
    "wt+d+pU#@9HuSGi<7v(wpJt?_X~6!$)ZBJ@n}wk?JGi-SPO>YPK5xB>=ZOg|=ft^?a<(V@cgeDZa78!58mgBY>DJBEIH|&1&3E&M"
    "tmFd3%!Uhw}_$J&%t*!Y`Es%^gvGI{wSJm{6rx{(N}${^M!UAy}B0%c87IRp_6y!w=`j`CfT<^5(E{<LTiU4$0xW<HK{@M;C{~zY"
    "fk$hUaVu61Nc9=qhZ7=@QHP{yO?cql@J?0FEDqpW|=vCh{Bk6S@5l^fnm_Xmojl-FH8o!%wRvpn1W@7|uDwoXtJHq4W2aJbxBLZ{"
    "C^xielSpV7kZ6TVtdbh};oGKApq_KYqChS8@Ll^K?$g7wEi~(0TG0dqd#7{SxgMM^E?a1x4=}ie9GYJ5oZ=5g@mu-"
    "F`vJJ3`8`d!)P|0rsOp=B4?tyXoHd0HSxCK)X}?^kO0Z?%@AZA@m85)bw<yfC<)+uk-"
    "p~<!9*d=<3&aH^jQcWtiOyo_}IIzmYTdTrmH0v{w(G4?h7;#ud_l@r!S(+OzhpZ(#N0Nu}Q-"
    "UYNRTuG9GvMp6v?n`*nP;{>zt(dQKt_zC1HY^KJOxABiyu<vVMiG$9!dpG23eUJJV=CxPMYZfkcZ~6K6JqjtRv7!RCz{qZMwlU=l"
    "({@cGO!33X1+3%4cOUaO*pf5hhlg+83{Edve2^+a`S$Q)GO^(3{xXjT%;TTOcyX-G$NO-"
    "I`>?sV{`IOX1z$G4h?jp+CQEHwpYt(5=8Ab>mJZn>{qod(D5Bf9ob{*aKohg&$%7DEt~ezduHwC%$rd@YG`??l?fHFL;N&=auC$S"
    "}yD6JloY}J37IQ{{|NdfY!$_GDcKER*9o}Ewe7b@jf6XyZp(nZws96#E?#c=%y0-"
    "#;Dk?S2CVYKV8{qUYNGBG+$*%3CL+TD!;fr1C2_t=WY8qP}0rX<&+L@&**O{19@G^YalUS%FhLMe1{9+M#0*lBFHNtlozSMBm>@a"
    "Sr;{c^ale2NK(#wJQG*n(GOe^aKK`#&4+Btk)BYJDQPVFUdo~zWJbr{!5l46g6y)ZH<!EKP9DQ-"
    "CN65wUzB84bvCTVoqN=KnFl6s<fV$5r;3^qguw-aFhU$|7x%9YYpJlB7nz_PD}=ql)bGaR<a9hLi(1W%C!uXxHbX0;%m5UZ2tDn^"
    "+lWr>C{P9ZP~THR@-"
    "6fBl3s+8y=P~WlM__xLX>qUHZwpP0&1TV2(9WsLgu8jwOWm?dYzB_m{E%l5XT60<6Nx0WDaVF(UK=8aZ`WP`+8(S-"
    "8Vef|B*gHqj4Tq$AY`YzTdBLq+;MS=KmVE}WYXnxkAldy#vg-t3b-"
    "#AI1hg+fS9=R*R|~h=P7ysjXxeF@)ic4UtYeJ2lW3>yne_Ikb?@VxwjHFW$Fa{n!s*4x{XLU~#|QR1i^qDQ0sBb<Hj3Mt-"
    "~jLKZ<p6!t_QHXN4MX81dM~NobueAyrW)lrC0NUi)%Ohs*cs7%QttupLopnv0D?5+f}^QJc%$Htksbq=zy-hglRont~M_~t26V_Z"
    "gU2|9FRO!99ThiXM(^s3G;f<JsX93t*nloqOFr5U2DzP<27}K;H}M9+TP5_rlDEgwPDS0EVaksSb5>(F-"
    "aKu&v&Dn(becvRZedQaZ}v|M6H4?cV!}^9h(Su5DK;J$;9^N!S6N*YWd20u^~NS1k{eqP@BX)y;zkV-"
    ">UTKYUE(Lu#ofR&8Mdff0}8@iv{7aEeN|3@ZVuT)7Terf1{b^PRr(@OwT){h;#r$cNtH#mAQ2@0Q%UGM4KK>Pw9s44@%1?zdk%VJ"
    "iR#nWq|u;aCr9S=i%Vp@!R7c-"
    "wpN{rLKxGTk+g2M+0uS%vIHVTkh1o!+3pppD&pjid4IIE;y=d8MoZkfGqj6#kmV@9h7r<GhQfIml2Uv-"
    "@(11cglNb<!HeVxmcKwe*V_zR0%@t)mQuNzK0pFe&|7C?jCxucYORjx&o-"
    "aZt=&P_}fFX+2e`qFPou$x{L9ju@#>byQWvJ?Yb~~UfO;BN}nhL-vBIy*jf#i)D0fq@@dzXp|f{)mpN}<ghnPeeUmz@yk`-"
    "3+{CX<k(Xe83YF1N=%*Zgw~mhA;B%(kxcWbx4F-"
    "Q5<Qlx{)l9+G%@zOT@HUGZmLR5pxotYl%++bl$=X~it+@22lut3^)%;IQetFmLfBXIa0gZNgfd"
)
SOURCE_PATHS = (
    ROOT_DIR
    / "configs/research-os/m4-v2-marginal-static-historical-identity-adoption-source-v1.json",
    ROOT_DIR
    / "configs/research-os/m4-v2-temporal-marginal-increment-source-v3.json",
    ROOT_DIR
    / "configs/research-os/m4-v2-joint-residual-increment-source-v3.json",
    ROOT_DIR / "configs/research-os/m4-v2-global-routing-source-v1.json",
)

EXPECTED_ARTIFACT_TYPES = {
    "M4V2BranchDecisionArtifact",
    "M4V2BranchDecisionReplayArtifact",
    "M4V2TemporalMarginalIncrementDesignArtifact",
    "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact",
    "M4V2TemporalMarginalIncrementHealthAggregateArtifact",
    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
    "M4V2TemporalMarginalIncrementCandidateModelArtifact",
    "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
    "M4V2TemporalMarginalIncrementScientificFailureArtifact",
    "M4V2JointResidualIncrementDesignArtifact",
    "M4V2JointResidualIncrementPreregistrationArtifact",
    "M4V2JointResidualMaximumEntropyBaselineArtifact",
    "M4V2JointResidualMeasurementHealthArtifact",
    "M4V2JointResidualHistoricalExecutionArtifact",
    "M4V2JointResidualCandidateModelArtifact",
    "M4V2JointResidualProducerCompletionArtifact",
    "M4V2JointResidualScientificFailureArtifact",
}

# Every numbered obligation in Request487 is intentionally mapped to at least one
# executable test below.  The matrix is itself checked so a future edit cannot
# silently drop one of the 45 frozen acceptance obligations.
ACCEPTANCE_MATRIX = {
    1: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    2: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    3: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    4: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    5: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    6: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    7: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    8: "test_marginal_identity_adoption_is_categorical_result_blind_and_singular",
    9: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    10: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    11: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    12: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    13: "test_resolver_global_route_and_four_and_p3_barrier",
    14: "test_resolver_global_route_and_four_and_p3_barrier",
    15: "test_global_router_is_finite_categorical_and_replay_is_pure",
    16: "test_global_router_is_finite_categorical_and_replay_is_pure",
    17: "test_global_router_is_finite_categorical_and_replay_is_pure",
    18: "test_global_router_repair_and_partial_positive_never_adaptive",
    19: "test_global_router_repair_and_partial_positive_never_adaptive",
    20: "test_resolver_global_route_and_four_and_p3_barrier",
    21: "test_resolver_global_route_and_four_and_p3_barrier",
    22: "test_resolver_global_route_and_four_and_p3_barrier",
    23: "test_resolver_global_route_and_four_and_p3_barrier",
    24: "test_p4_requires_completed_p3_and_explicit_pass",
    25: "test_p4_requires_completed_p3_and_explicit_pass",
    26: "test_source_contracts_exact_closure_and_digest_drift_fail_closed",
    27: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    28: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    29: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    30: "test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history",
    31: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    32: "test_zero_compute_parent_stop_chain_replays_and_global_route",
    33: "test_acceptance_matrix_covers_all_45_required_goal_tests",
    34: "test_governance_digest_equivalence_and_lifecycle_fail_closed",
    35: "test_governance_constants_and_all_source_contract_seals",
    36: "test_successor_v2_estimator_identity_rejects_predecessor_v1",
    37: "test_fixed_null_warmup_exact_alias_and_falsifiers",
    38: "test_temporal_composite_and_joint_chronology_contracts",
    39: "test_synthetic_cartesian_grid_seed_and_count_invariance",
    40: "test_all_17_artifact_types_nested_lineage_paths_and_cardinalities",
    41: "test_holm_lineage_and_formal_one_rules_fail_before_workload",
    42: "test_global_router_is_finite_categorical_and_replay_is_pure",
    43: "test_atomic_publication_crash_reconciliation_and_conflicts",
    44: "test_engineering_boundary_has_zero_runtime_or_operator_actions",
    45: "test_resolver_global_route_and_four_and_p3_barrier",
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _manifest_payload() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _recovery_input_payload() -> dict[str, Any]:
    """Decode the immutable, result-blind recovery boundary under test."""

    encoded = RECOVERY_INPUT_FIXTURE_B85.encode("ascii")
    assert hashlib.sha256(encoded).hexdigest() == RECOVERY_INPUT_FIXTURE_B85_SHA256
    compressed = base64.b85decode(encoded)
    assert hashlib.sha256(compressed).hexdigest() == RECOVERY_INPUT_COMPRESSED_SHA256
    canonical = zlib.decompress(compressed)
    assert hashlib.sha256(canonical).hexdigest() == RECOVERY_INPUT_CANONICAL_SHA256
    payload = json.loads(canonical)
    typed = ControlPlaneManifest.from_dict(payload)
    assert typed.artifact_digest == RECOVERY_INPUT_MANIFEST_DIGEST
    snapshot = ResearchOSControlPlane().resolve(typed)
    assert snapshot.snapshot_digest == RECOVERY_INPUT_SNAPSHOT_DIGEST
    assert m4_v2_canonical_json(typed.to_dict(include_digest=True)).encode() == canonical
    return json.loads(canonical)


def test_recovery_input_fixture_matches_live_database_when_available() -> None:
    repository = PostgresResearchOSRepository()
    try:
        with repository.connection_factory():
            pass
    except psycopg.OperationalError:
        pytest.skip("configured PostgreSQL is unavailable for explicit integration check")

    typed = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    assert typed.artifact_digest == RECOVERY_INPUT_MANIFEST_DIGEST
    assert typed.to_dict(include_digest=True) == _recovery_input_payload()


def _successor_payload() -> dict[str, Any]:
    payload = _recovery_input_payload()
    for builder, path in zip(
        (
            marginal_builder.build_manifest,
            temporal_builder.build_manifest,
            joint_builder.build_manifest,
            global_builder.build_manifest,
        ),
        SOURCE_PATHS,
        strict=True,
    ):
        digest = json.loads(path.read_text(encoding="utf-8"))["artifact_digest"]
        payload, dry_run = builder(payload, digest)
        assert dry_run["status"] == "VERIFIED"
        for key in (
            "existing_goal_deletions",
            "existing_fact_deletions",
            "existing_state_regressions",
        ):
            if key in dry_run:
                assert dry_run[key] == 0
        assert dry_run["import_performed"] is False
    return payload


def _without_manifest_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(payload))
    result.pop("artifact_digest", None)
    result.pop("manifest_digest", None)
    return result


def _task(payload: Mapping[str, Any], task_key: str) -> dict[str, Any]:
    matches = [
        copy.deepcopy(item) for item in payload["tasks"] if item["task_key"] == task_key
    ]
    assert len(matches) == 1
    return matches[0]


def _dependency_tuples(task: Mapping[str, Any]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            item["dependency_type"],
            item["target_key"],
            item["required_status"],
        )
        for item in task["dependencies"]
    )


def _set_task_completed(payload: dict[str, Any], task_key: str) -> None:
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    typed_task = next(task for task in manifest.tasks if task.task_key == task_key)
    task = next(item for item in payload["tasks"] if item["task_key"] == task_key)
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"
    if typed_task.requested_capability is not None:
        _add_facts(
            payload,
            mainline_completion_fact(
                task=typed_task,
                execution_id=_digest(f"completed-execution:{task_key}"),
            ),
        )


def _add_facts(payload: dict[str, Any], *facts: str) -> None:
    payload["facts"]["artifacts"] = sorted(
        set(payload["facts"]["artifacts"]).union(facts)
    )
    payload.pop("artifact_digest", None)
    payload.pop("manifest_digest", None)


def _resolution(manifest: ControlPlaneManifest, task_key: str):
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return next(item for item in snapshot.resolutions if item.task_key == task_key)


def _registration(
    artifact: Mapping[str, Any],
    *,
    task_key: str,
    execution_id: str,
    slug: str,
    filename: str,
) -> dict[str, Any]:
    record = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
        task_digest=_digest(f"task:{task_key}"),
        artifact_digest=str(artifact["artifact_digest"]),
        artifact_type=str(artifact["artifact_type"]),
        schema_version=str(artifact["schema_version"]),
        artifact_path=(
            f"runtime/research-os/mainline/tasks/{task_key}/{execution_id}/"
            f"artifacts/{slug}/{artifact['artifact_digest']}/{filename}"
        ),
        parent_digests=tuple(artifact["parent_digests"]),
        git_commit=GIT_COMMIT,
    )
    return {"registration_digest": record.registration_digest, **jsonable(record)}


class _TrackingIdentity(dict[str, Any]):
    def __init__(self, value: Mapping[str, Any]) -> None:
        super().__init__(value)
        self.reads: list[str] = []

    def get(self, key: str, default: Any = None) -> Any:
        self.reads.append(key)
        return super().get(key, default)

    def __getitem__(self, key: str) -> Any:
        self.reads.append(key)
        return super().__getitem__(key)


def _marginal_pair(*, evidence: str = "NEGATIVE", health: str = "PASS"):
    evaluated = health == "PASS"
    accepted = evaluated and evidence == "POSITIVE"
    categorical = {
        "measurement_health": health,
        "historical_run_status": "COMPLETE",
        "historical_evidence": evidence,
        "accepted_for_downstream_baseline": accepted,
        "accepted_model_artifact_digest": (
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_artifact_digest": (
            marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST if evaluated else None
        ),
        "baseline_source_model_artifact_digest": None,
        "endpoint_digest": _digest("marginal-endpoint"),
    }
    decision_execution = _digest("marginal-decision-execution")
    decision = marginal.build_marginal_static_branch_decision(
        categorical_identity=categorical,
        producer_execution_id=decision_execution,
        parent_digests=(
            _digest("marginal-source"),
            marginal.MARGINAL_STATIC_GATE_ARTIFACT_DIGEST,
        ),
    ).to_dict()
    decision_registration = _registration(
        decision,
        task_key=marginal.MARGINAL_STATIC_DECISION_TASK_KEY,
        execution_id=decision_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    replay_execution = _digest("marginal-replay-execution")
    replay = marginal.build_marginal_static_branch_decision_replay(
        decision=decision,
        source_contract_digest=_digest("marginal-source"),
        decision_registration_digest=decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "marginal-producer-execution-artifact"
        ),
        replay_execution_id=replay_execution,
    ).to_dict()
    replay_registration = _registration(
        replay,
        task_key=marginal.MARGINAL_STATIC_REPLAY_TASK_KEY,
        execution_id=replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    return {
        "decision": decision,
        "decision_registration": decision_registration,
        "replay": replay,
        "replay_registration": replay_registration,
    }


def _zero_compute_records(*, marginal_evidence: str = "NEGATIVE", health: str = "PASS"):
    marginal_record = _marginal_pair(evidence=marginal_evidence, health=health)
    temporal_execution = _digest("temporal-decision-execution")
    temporal_decision, temporal_completion = (
        temporal.build_temporal_parent_not_accepted_path(
            source_contract_digest=_digest("temporal-source"),
            preregistration_artifact_digest=_digest("temporal-preregistration"),
            marginal_decision_artifact=marginal_record["decision"],
            marginal_replay_artifact=marginal_record["replay"],
            producer_execution_id=temporal_execution,
        )
    )
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_replay_registration = _registration(
        temporal_replay,
        task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
        execution_id=temporal_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": temporal_replay_registration,
    }

    joint_execution = _digest("joint-decision-execution")
    joint_decision, joint_completion = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_replay_registration = _registration(
        joint_replay,
        task_key=joint.JOINT_REPLAY_TASK_KEY,
        execution_id=joint_replay_execution,
        slug="branch-decision-replay",
        filename="replay.json",
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": joint_replay_registration,
    }
    return (
        (marginal_record, temporal_record, joint_record),
        (temporal_completion, joint_completion),
    )


def _accepted_records():
    marginal_record = _marginal_pair(evidence="POSITIVE")

    temporal_execution = _digest("accepted-temporal-decision-execution")
    temporal_model = _digest("accepted-temporal-model")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=temporal_model,
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("accepted-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("accepted-joint-decision-execution")
    joint_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        scientific_decision="BRANCH_INFORMATION_ACCEPTED",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="POSITIVE",
        accepted_for_downstream_baseline=True,
        accepted_model_artifact_digest=_digest("accepted-joint-model"),
        baseline_artifact_digest=_digest("accepted-joint-baseline"),
        baseline_source_model_artifact_digest=temporal_model,
        producer_task_key=joint.JOINT_PRODUCER_TASK_KEY,
        producer_execution_id=joint_execution,
        parent_digests=(
            _digest("joint-source"),
            _digest("joint-preregistration"),
            temporal_decision["artifact_digest"],
            temporal_replay["artifact_digest"],
        ),
    ).to_dict()
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("accepted-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "accepted-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def _partial_positive_records():
    """One valid positive ancestor plus an inconclusive Temporal and stopped Joint."""

    marginal_record = _marginal_pair(evidence="POSITIVE")
    temporal_execution = _digest("partial-temporal-decision-execution")
    temporal_decision = M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        estimand_digest=M4_V2_ESTIMAND_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
        decision_path="EVALUATED_COMPLETE",
        terminal_decision="INCONCLUSIVE_DUE_TO_POWER",
        scientific_decision="INCONCLUSIVE_DUE_TO_POWER",
        evaluation_status="COMPLETE",
        measurement_health="PASS",
        historical_evidence="INCONCLUSIVE",
        accepted_for_downstream_baseline=False,
        accepted_model_artifact_digest=_digest("partial-temporal-model"),
        baseline_artifact_digest=marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
        baseline_source_model_artifact_digest=(
            marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST
        ),
        producer_task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        producer_execution_id=temporal_execution,
        parent_digests=(
            _digest("temporal-source"),
            _digest("temporal-preregistration"),
            marginal_record["decision"]["artifact_digest"],
            marginal_record["replay"]["artifact_digest"],
        ),
    ).to_dict()
    temporal_decision_registration = _registration(
        temporal_decision,
        task_key=temporal.TEMPORAL_PRODUCER_TASK_KEY,
        execution_id=temporal_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    temporal_replay_execution = _digest("partial-temporal-replay-execution")
    temporal_replay = temporal.build_temporal_branch_replay(
        source_contract_digest=_digest("temporal-source"),
        decision_artifact=temporal_decision,
        decision_registration_digest=temporal_decision_registration[
            "registration_digest"
        ],
        decision_producer_execution_artifact_digest=_digest(
            "partial-temporal-producer-execution-artifact"
        ),
        replay_execution_id=temporal_replay_execution,
    )
    temporal_record = {
        "decision": temporal_decision,
        "decision_registration": temporal_decision_registration,
        "replay": temporal_replay,
        "replay_registration": _registration(
            temporal_replay,
            task_key=temporal.TEMPORAL_REPLAY_TASK_KEY,
            execution_id=temporal_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }

    joint_execution = _digest("partial-joint-decision-execution")
    joint_decision, _ = joint.build_joint_parent_not_accepted_path(
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-preregistration"),
        marginal_decision_artifact=marginal_record["decision"],
        marginal_replay_artifact=marginal_record["replay"],
        temporal_decision_artifact=temporal_decision,
        temporal_replay_artifact=temporal_replay,
        producer_execution_id=joint_execution,
    )
    joint_decision_registration = _registration(
        joint_decision,
        task_key=joint.JOINT_PRODUCER_TASK_KEY,
        execution_id=joint_execution,
        slug="branch-decision",
        filename="decision.json",
    )
    joint_replay_execution = _digest("partial-joint-replay-execution")
    joint_replay = joint.build_joint_branch_replay(
        source_contract_digest=_digest("joint-source"),
        decision_artifact=joint_decision,
        decision_registration_digest=joint_decision_registration["registration_digest"],
        decision_producer_execution_artifact_digest=_digest(
            "partial-joint-producer-execution-artifact"
        ),
        replay_execution_id=joint_replay_execution,
    )
    joint_record = {
        "decision": joint_decision,
        "decision_registration": joint_decision_registration,
        "replay": joint_replay,
        "replay_registration": _registration(
            joint_replay,
            task_key=joint.JOINT_REPLAY_TASK_KEY,
            execution_id=joint_replay_execution,
            slug="branch-decision-replay",
            filename="replay.json",
        ),
    }
    return marginal_record, temporal_record, joint_record


def test_acceptance_matrix_covers_all_45_required_goal_tests() -> None:
    assert tuple(ACCEPTANCE_MATRIX) == tuple(range(1, 46))
    test_names = {
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    }
    assert set(ACCEPTANCE_MATRIX.values()).issubset(test_names)


def test_additive_manifest_preserves_p2_p2r_structural_terminal_and_history() -> None:
    before = ControlPlaneManifest.from_dict(_recovery_input_payload()).to_dict(
        include_digest=False
    )
    after = ControlPlaneManifest.from_dict(_successor_payload()).to_dict(
        include_digest=False
    )
    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in after["tasks"]}
    assert len(after_tasks) == len(before_tasks)
    assert marginal_builder.REPLAY_TASK_KEY in before_tasks
    assert marginal_builder.REPLAY_TASK_KEY not in after_tasks
    assert marginal_builder.REPLAY_RECOVERY_TASK_KEY not in before_tasks
    assert marginal_builder.REPLAY_RECOVERY_TASK_KEY in after_tasks

    revised = {
        marginal_builder.REPLAY_TASK_KEY,
        temporal_builder.DESIGN_TASK,
        temporal_builder.PREREG_TASK,
        temporal_builder.PRODUCER_TASK,
        temporal_builder.REPLAY_TASK,
        joint_builder.DESIGN_TASK,
        joint_builder.PREREG_TASK,
        joint_builder.PRODUCER_TASK,
        joint_builder.REPLAY_TASK,
        global_builder.GLOBAL_TASK,
    }
    for task_key, task in before_tasks.items():
        if task_key not in revised:
            assert after_tasks[task_key] == task
        elif task_key != marginal_builder.REPLAY_TASK_KEY:
            for state_field in (
                "status",
                "completion_classification",
                "superseded_by_task_digest",
            ):
                assert after_tasks[task_key].get(state_field) == task.get(state_field)
    recovery = after_tasks[marginal_builder.REPLAY_RECOVERY_TASK_KEY]
    assert recovery["status"] == "draft"
    assert recovery["completion_classification"] == "INTEGRATION_PENDING"
    assert (
        recovery["metric_contract"]["recovery_lineage"]
        == marginal_builder.REPLAY_RECOVERY_LINEAGE
    )
    assert recovery["metric_contract"]["recovery_lineage_digest"] == (
        marginal_builder.REPLAY_RECOVERY_LINEAGE_DIGEST
    )
    assert recovery["input_artifact_digests"] == [
        "f078eed2de707bf1e0ed80495eb9955bd8a909e170fed3318110574f7722e3bb"
    ]
    canonical_keys = {
        marginal_builder.REPLAY_RECOVERY_TASK_KEY,
        *(revised - {marginal_builder.REPLAY_TASK_KEY}),
    }
    for task_key in canonical_keys:
        integration = after_tasks[task_key]["metric_contract"]["mainline_integration"]
        assert "downstream_consumer" in integration
        assert "evidence_progress_rule" in integration
        assert "next_consumer" not in integration
        assert "evidence_rule" not in integration
    for fact_type, facts in before["facts"].items():
        assert set(facts).issubset(after["facts"][fact_type])

    p2 = after_tasks["m4-p2-synthetic-measurement-validation"]
    assert p2 == before_tasks["m4-p2-synthetic-measurement-validation"]
    p2r = after_tasks[P2R_TASK_KEY]
    assert p2r["status"] == "draft"
    assert p2r["completion_classification"] == "INTEGRATION_PENDING"
    assert all(
        dependency["target_key"] != P2R_TASK_KEY
        for key in (
            PREDICTIVE_P3_TASK_KEY,
            PREDICTIVE_P4_TASK_KEY,
            PREDICTIVE_P5_TASK_KEY,
        )
        for dependency in after_tasks[key]["dependencies"]
    )
    assert not any(
        "promotion:allowed" in fact.lower() for fact in after["facts"]["artifacts"]
    )

    structural_goal = next(
        item
        for item in after["goals"]
        if item["goal_key"] == "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY"
    )
    assert (
        "NO_STABLE_STRUCTURAL_UTILITY"
        in structural_goal["target_metric_manifest"]["allowed_decisions"]
    )
    assert structural_goal["target_metric_manifest"]["prediction_promotion"] == "closed"


def test_recovery_entry_audit_rejects_manifest_ready_and_event_lineage_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_payload = _recovery_input_payload()
    source_digest = json.loads(SOURCE_PATHS[0].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    tampered = copy.deepcopy(input_payload)
    tampered.pop("manifest_digest")
    _add_facts(tampered, "unexpected-ready-enabling-fact")
    with pytest.raises(
        AdditiveManifestMigrationError,
        match="manifest_replay_recovery_input_manifest_digest_changed",
    ):
        marginal_builder.build_manifest(tampered, source_digest)

    exact_metadata = tuple(
        {
            "sequence": sequence,
            "event_type": event_type,
            "event_digest": event_digest,
            "execution_id": (
                "a41b900ce663f4f6a6f16b5429f70270954daee019c746f89d255b9daef5b9b0"
            ),
            "task_key": marginal_builder.REPLAY_TASK_KEY,
            "task_digest": (
                "26aefc4e9e1ae7e2673acef28f7630f85b90baf34e26e1abe8e047d2dd478832"
            ),
            "control_plane_key": CONTROL_PLANE_KEY,
            "manifest_digest": (
                "c7c827b3dc41eaecb07d80fd150025de4c2e179e8a6cdfd204ebd4ab191ec56c"
            ),
            "capability": "m4_v2_marginal_static_historical_branch_decision_replay",
        }
        for sequence, event_type, event_digest in (
            (
                0,
                "started",
                "85eeba6a9dd2f477267705e0aa7f80b53e6450021563dd5a54a5146e10431065",
            ),
            (
                1,
                "failed",
                "338f84f5dafab3ff55a2566e3e4cf437769707674722d9b9f7335510d8f0b7b4",
            ),
        )
    )
    verify_failed_replay_recovery_event_metadata(exact_metadata)
    for index in range(len(exact_metadata)):
        altered = [dict(item) for item in exact_metadata]
        altered[index]["event_digest"] = _digest(f"forged-event-{index}")
        with pytest.raises(
            AdditiveManifestMigrationError,
            match="failed_execution_event_metadata_changed",
        ):
            verify_failed_replay_recovery_event_metadata(altered)

    class _Cursor:
        def __init__(
            self,
            rows: Sequence[Mapping[str, Any]],
            *,
            current_digest: str = (
                "1331950e7f2c74ee8db22bb3383d1defb241b4bee0253d2fedbb8cde065cb470"
            ),
            current_payload: Mapping[str, Any] | None = None,
        ) -> None:
            self.rows = tuple(dict(item) for item in rows)
            self.current_digest = current_digest
            self.current_payload = current_payload

        def execute(self, statement: str, _params: object) -> SimpleNamespace:
            if "FROM research_os_control_planes" in statement:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "current_manifest_digest": self.current_digest
                    }
                )
            if "FROM research_os_manifests" in statement:
                return SimpleNamespace(
                    fetchone=lambda: (
                        None
                        if self.current_payload is None
                        else {"manifest_json": dict(self.current_payload)}
                    )
                )
            if "FROM research_os_task_definitions" in statement:
                return SimpleNamespace(
                    fetchall=lambda: (
                        {
                            "task_digest": (
                                "26aefc4e9e1ae7e2673acef28f7630f85b90baf34e26e1abe8e047d2dd478832"
                            ),
                            "declared_status": "failed",
                            "completion_classification": "INTEGRATED",
                            "superseded_by_task_digest": None,
                        },
                        {
                            "task_digest": (
                                "ee575d4109b055e1988ae493e2a6a913704624d8e611063f707aed08d34e344e"
                            ),
                            "declared_status": "superseded",
                            "completion_classification": "INTEGRATION_PENDING",
                            "superseded_by_task_digest": (
                                "26aefc4e9e1ae7e2673acef28f7630f85b90baf34e26e1abe8e047d2dd478832"
                            ),
                        },
                    )
                )
            if "FROM research_os_mainline_execution_events" in statement:
                return SimpleNamespace(fetchall=lambda: self.rows)
            raise AssertionError(statement)

    successor = ControlPlaneManifest.from_dict(_successor_payload())
    PostgresResearchOSRepository._verify_m4_v2_failed_replay_recovery_import(
        _Cursor(exact_metadata),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=successor,
    )
    PostgresResearchOSRepository._verify_m4_v2_failed_replay_recovery_import(
        _Cursor(exact_metadata, current_digest=successor.artifact_digest),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=successor,
    )

    successor_payload = successor.to_dict(include_digest=False)
    successor_payload["facts"]["artifacts"] = sorted(
        {*successor_payload["facts"]["artifacts"], "post-recovery-state-progress"}
    )
    progressed = ControlPlaneManifest.from_dict(successor_payload)
    PostgresResearchOSRepository._verify_m4_v2_failed_replay_recovery_import(
        _Cursor(
            exact_metadata,
            current_digest=successor.artifact_digest,
            current_payload=successor.to_dict(include_digest=True),
        ),
        control_plane_key=CONTROL_PLANE_KEY,
        manifest=progressed,
    )

    forged_payload = successor.to_dict(include_digest=False)
    next(
        item
        for item in forged_payload["tasks"]
        if item["task_key"] == marginal_builder.REPLAY_RECOVERY_TASK_KEY
    )["priority"] += 1
    forged_current = ControlPlaneManifest.from_dict(forged_payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="current_manifest_lineage_changed",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_replay_recovery_import(
            _Cursor(
                exact_metadata,
                current_digest=forged_current.artifact_digest,
                current_payload=forged_current.to_dict(include_digest=True),
            ),
            control_plane_key=CONTROL_PLANE_KEY,
            manifest=progressed,
        )
    drifted_rows = (
        exact_metadata[:-1],
        (*exact_metadata, dict(exact_metadata[-1])),
        tuple(reversed(exact_metadata)),
        (
            {**exact_metadata[0], "event_digest": _digest("forged-event")},
            exact_metadata[1],
        ),
    )
    for rows in drifted_rows:
        with pytest.raises(
            ResearchOSValidationError,
            match="failed_execution_event_metadata_changed",
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_replay_recovery_import(
                _Cursor(rows),
                control_plane_key=CONTROL_PLANE_KEY,
                manifest=successor,
            )

    class _Context:
        def __init__(self, value: object) -> None:
            self.value = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(self, *_args: object) -> None:
            return None

    class _NoWriteConnection:
        def cursor(self, **_kwargs: object) -> _Context:
            return _Context(SimpleNamespace())

    preflight_calls: list[str] = []

    def reject_before_write(
        _cursor: object, *, control_plane_key: str, manifest: object
    ) -> None:
        assert control_plane_key == CONTROL_PLANE_KEY
        assert manifest is not None
        preflight_calls.append("preflight")
        raise ResearchOSValidationError("lineage_preflight_rejected")

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_replay_recovery_import",
        staticmethod(reject_before_write),
    )
    repository = PostgresResearchOSRepository(
        lambda: _Context(_NoWriteConnection())  # type: ignore[arg-type]
    )
    with pytest.raises(ResearchOSValidationError, match="lineage_preflight_rejected"):
        repository.import_manifest(
            control_plane_key=CONTROL_PLANE_KEY,
            payload=successor.to_dict(include_digest=True),
        )
    assert preflight_calls == ["preflight"]


def test_recovery_status_projection_uses_only_the_new_active_replay() -> None:
    manifest = ControlPlaneManifest.from_dict(_successor_payload())
    verified = validate_m4_v2_successor_structure(manifest)
    assert verified["status"] == "VERIFIED"
    assert M4_V2_SUCCESSOR_TASKS["marginal_replay"] == (
        marginal_builder.REPLAY_RECOVERY_TASK_KEY
    )
    assert marginal_builder.REPLAY_TASK_KEY not in {
        task.task_key for task in manifest.tasks
    }


def test_global_downstream_route_map_is_exact_and_unknown_route_fails_closed() -> None:
    payload = _successor_payload()
    global_task = _task(payload, global_builder.GLOBAL_TASK)
    integration = global_task["metric_contract"]["mainline_integration"]
    downstream = integration["downstream_consumer"]
    assert downstream == global_builder.GLOBAL_DOWNSTREAM_CONSUMER
    assert hashlib.sha256(downstream.encode()).hexdigest() == (
        "5821fa0f008bf14548be0d2faa5d007e150d116ceaecbb39b170f0ca53917d60"
    )
    mapping = json.loads(downstream)
    assert mapping["ADAPTIVE_RESEARCH_ELIGIBLE"] == (
        "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
    )
    assert all(
        consumer != "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
        for route, consumer in mapping.items()
        if route != "ADAPTIVE_RESEARCH_ELIGIBLE"
    )
    assert "UNKNOWN_ROUTE" not in mapping


def test_marginal_identity_adoption_is_categorical_result_blind_and_singular() -> None:
    tracked = _TrackingIdentity(
        {
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "historical_evidence": "NEGATIVE",
            "accepted_for_downstream_baseline": False,
            "accepted_model_artifact_digest": marginal.MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST,
            "baseline_artifact_digest": marginal.MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST,
            "baseline_source_model_artifact_digest": None,
            "endpoint_digest": _digest("endpoint"),
        }
    )
    first = marginal.build_marginal_static_branch_decision(
        categorical_identity=tracked,
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    second = marginal.build_marginal_static_branch_decision(
        categorical_identity=dict(tracked),
        producer_execution_id=_digest("categorical-producer"),
        parent_digests=(_digest("source"), _digest("registered-gate")),
    )
    assert first.artifact_digest == second.artifact_digest
    assert first.branch_id == "MARGINAL_STATIC"
    assert first.terminal_decision == "NO_DETECTABLE_INFORMATION"
    assert first.producer_task_key == marginal.MARGINAL_STATIC_DECISION_TASK_KEY
    assert not {
        "raw_p_value",
        "fold_scores",
        "historical_fold_scores",
        "prediction_results",
    }.intersection(tracked.reads)

    polluted = dict(tracked)
    polluted["raw_primary_p_value"] = 0.001
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="result_payload"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=polluted,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )
    wrong_identity = dict(tracked)
    wrong_identity["accepted_model_artifact_digest"] = _digest("not-marginal")
    with pytest.raises(
        marginal.MarginalStaticBranchDecisionError, match="identity_mismatch"
    ):
        marginal.build_marginal_static_branch_decision(
            categorical_identity=wrong_identity,
            producer_execution_id=_digest("categorical-producer"),
            parent_digests=(_digest("source"), _digest("registered-gate")),
        )


def _governance_fixture(identifier: int, *, failed: bool = False):
    request = {
        "id": identifier,
        "request_key": f"request-{identifier}",
        "request_type": "engineering_implementation"
        if failed
        else "research_scheduler_request",
        "requested_by_role": "research",
        "requested_by": "research:fixture",
        "hypothesis_id": None,
        "experiment_id": None,
        "parent_request_id": None,
        "title": "result-blind fixture",
        "summary": "metadata only",
        "payload": {"result_payload_reads": 0, "computation": 0},
        "status": "failed" if failed else "completed",
        "risk_level": "critical",
        "requires_review": True,
        "metadata": {"scientific_result_read": False},
    }
    execution_id = identifier + 1000
    execution = {
        "id": execution_id,
        "request_id": identifier,
        "executor_role": "engineering" if failed else "research",
        "executor_id": "fixture:executor",
        "execution_type": "isolated",
        "status": "failed" if failed else "completed",
        "environment": "isolated",
        "run_id": f"run-{execution_id}",
        "started_at": "2026-08-11T00:00:00+00:00",
        "completed_at": "2026-08-11T00:00:01+00:00",
        "artifact_paths": [],
        "created_at": "2026-08-11T00:00:00+00:00",
    }
    decision_count = 3 if failed else 2
    decisions = []
    for offset in range(decision_count):
        decision_id = identifier * 10 + offset
        final = offset == decision_count - 1
        decisions.append(
            {
                "id": decision_id,
                "request_id": identifier,
                "previous_status": "running" if final else "under_review",
                "new_status": (
                    "failed"
                    if failed and final
                    else "completed"
                    if final
                    else "approved"
                ),
                "decision_code": (
                    "execution_failed"
                    if failed and final
                    else "execution_completed"
                    if final
                    else "request_approved"
                ),
                "summary": f"decision-{offset}",
                "reason": {"result_blind": True, "result_payload_reads": 0},
                "decided_by_role": "reviewer",
                "decided_by": "reviewer:fixture",
                "decided_at": f"2026-08-11T00:00:0{offset}+00:00",
                "created_at": f"2026-08-11T00:00:0{offset}+00:00",
            }
        )
    return request, execution, decisions


class _Rows:
    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.rows = [copy.deepcopy(dict(row)) for row in rows]

    def fetchall(self):
        return copy.deepcopy(self.rows)


class _GovernanceCursor:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.fixture = fixture
        self.sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql: str, _params: Any):
        normalized = " ".join(sql.split())
        self.sql.append(normalized)
        if "FROM agent_requests" in normalized:
            return _Rows(self.fixture["requests"])
        if (
            "FROM agent_request_executions" in normalized
            and "count(*)" not in normalized
        ):
            return _Rows(self.fixture["executions"])
        if "decision_code = 'request_approved'" in normalized:
            return _Rows(self.fixture["counts"])
        if "FROM agent_request_decisions" in normalized and "max(id)" not in normalized:
            return _Rows(self.fixture["decisions"])
        if "count(*) AS count" in normalized:
            return _Rows(self.fixture["counts"])
        if "max(id) AS last_decision_id" in normalized:
            return _Rows(self.fixture["last"])
        raise AssertionError(normalized)


class _GovernanceConnection:
    def __init__(self, cursor: _GovernanceCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return self._cursor


class _GovernanceRepository:
    def __init__(self, fixture: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self.cursor = _GovernanceCursor(fixture)

    def _connection_factory(self):
        return _GovernanceConnection(self.cursor)


def _synthetic_governance_contract():
    completed_request, completed_execution, completed_decisions = _governance_fixture(1)
    failed_request, failed_execution, failed_decisions = _governance_fixture(
        2, failed=True
    )
    completed_binding = {
        "request_id": 1,
        "execution_id": completed_execution["id"],
        "reviewer_approval_decision_id": completed_decisions[0]["id"],
        "completion_decision_id": completed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(
            completed_request
        ),
        "execution_metadata_digest": governance_execution_metadata_digest(
            completed_execution
        ),
        "reviewer_approval_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[0]
        ),
        "completion_decision_digest": governance_reviewer_decision_digest(
            completed_decisions[-1]
        ),
    }
    failed_binding = {
        "request_id": 2,
        "execution_id": failed_execution["id"],
        "approval_decision_id": failed_decisions[0]["id"],
        "start_decision_id": failed_decisions[1]["id"],
        "failure_decision_id": failed_decisions[-1]["id"],
        "request_identity_digest": governance_request_identity_digest(failed_request),
        "execution_metadata_digest": governance_execution_metadata_digest(
            failed_execution
        ),
        "approval_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[0]
        ),
        "start_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[1]
        ),
        "failure_decision_digest": governance_reviewer_decision_digest(
            failed_decisions[-1]
        ),
        "artifact_paths": [],
        "repository_files_changed": 0,
    }
    fixture = {
        "requests": [completed_request, failed_request],
        "executions": [completed_execution, failed_execution],
        "decisions": [*completed_decisions, *failed_decisions],
        "counts": [{"request_id": 1, "count": 1}, {"request_id": 2, "count": 1}],
        "last": [
            {"request_id": 1, "last_decision_id": completed_decisions[-1]["id"]},
            {"request_id": 2, "last_decision_id": failed_decisions[-1]["id"]},
        ],
    }
    return completed_binding, failed_binding, fixture


def test_governance_digest_equivalence_and_lifecycle_fail_closed(monkeypatch) -> None:
    request, execution, decisions = _governance_fixture(77)
    assert governance_request_identity_digest(
        request
    ) == governance_reference.governance_request_identity_digest(request)
    sanitized_execution = {
        key: value
        for key, value in execution.items()
        if key not in {"status", "completed_at", "artifact_paths"}
    }
    assert governance_execution_metadata_digest(
        sanitized_execution
    ) == governance_reference.governance_execution_metadata_digest(sanitized_execution)
    assert governance_reviewer_decision_digest(
        decisions[0]
    ) == governance_reference.governance_reviewer_decision_digest(decisions[0])
    for forbidden in (
        "result",
        "result_json",
        "execution_result",
        "error",
        "error_json",
    ):
        polluted = dict(sanitized_execution)
        polluted[forbidden] = {"must_not_be_read": True}
        with pytest.raises(ResearchOSValidationError, match="not_sanitized"):
            governance_execution_metadata_digest(polluted)

    completed_binding, failed_binding, fixture = _synthetic_governance_contract()
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS",
        (completed_binding,),
    )
    monkeypatch.setattr(
        supervisor_module,
        "M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING",
        failed_binding,
    )
    repository = _GovernanceRepository(fixture)
    supervisor_module._verify_m4_v2_successor_governance(agent_repository=repository)
    combined_sql = " ".join(repository.cursor.sql).lower()
    assert "result_json" not in combined_sql
    assert "error_json" not in combined_sql
    assert "artifact_paths_json as artifact_paths" in combined_sql

    for mutation in ("duplicate_execution", "later_decision", "artifact_path"):
        broken = copy.deepcopy(fixture)
        if mutation == "duplicate_execution":
            broken["counts"][0]["count"] = 2
        elif mutation == "later_decision":
            broken["last"][0]["last_decision_id"] += 100
        else:
            broken["executions"][0]["artifact_paths"] = ["forbidden.json"]
        with pytest.raises(
            supervisor_module.MainlineSupervisorError, match="lifecycle changed"
        ):
            supervisor_module._verify_m4_v2_successor_governance(
                agent_repository=_GovernanceRepository(broken)
            )

    reused_failed = copy.deepcopy(fixture)
    reused_failed["requests"][1]["status"] = "completed"
    reused_failed["executions"][1]["status"] = "completed"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="failed Engineering predecessor",
    ):
        supervisor_module._verify_m4_v2_successor_governance(
            agent_repository=_GovernanceRepository(reused_failed)
        )


def test_governance_constants_and_all_source_contract_seals() -> None:
    bindings = supervisor_module.M4_V2_SUCCESSOR_GOVERNANCE_BINDINGS
    failed = supervisor_module.M4_V2_FAILED_ENGINEERING_PREDECESSOR_BINDING
    assert [item["request_id"] for item in bindings] == [
        478,
        479,
        480,
        481,
        482,
        484,
        485,
        486,
    ]
    assert [item["execution_id"] for item in bindings] == [
        399,
        400,
        402,
        401,
        403,
        405,
        406,
        407,
    ]
    assert len(bindings) == 8
    assert sum(key.endswith("_digest") for item in bindings for key in item) == 32
    assert failed["request_id"] == 483
    assert failed["execution_id"] == 404
    assert failed["artifact_paths"] == []
    assert failed["repository_files_changed"] == 0
    assert sum(key.endswith("_digest") for key in failed) == 5

    assert supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN == (
        "4e787ebc1b13e1a16fe42b80054cb2a01f4c0b6b"
    )
    assert set(supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES) == {
        "marginal",
        "temporal",
        "joint",
        "global",
    }
    for family, spec in supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS.items():
        legacy = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        assert (
            legacy["artifact_digest"],
            legacy["source_set_digest"],
        ) == supervisor_module.M4_V2_HISTORICAL_SOURCE_IDENTITIES[family]
        assert len(legacy["source_entries"]) == 7
        if family in {"temporal", "joint"}:
            assert spec["selector"] == f"{family}_v3"
            assert spec["path"].endswith("source-v3.json")
            assert spec["historical_path"].endswith("source-v2.json")
        else:
            # Marginal and Global have no live selector after Request512.  Their
            # checked-out files are irrelevant to this audit-only verifier.
            assert "selector" not in spec


def test_zero_compute_parent_stop_chain_replays_and_global_route() -> None:
    records, completions = _zero_compute_records()
    temporal_completion, joint_completion = completions
    for record, branch_id in zip(records, M4_V2_BRANCH_IDS, strict=True):
        decision = validate_m4_v2_artifact_envelope(record["decision"])
        replay = validate_m4_v2_artifact_envelope(record["replay"])
        assert decision["body"]["branch_id"] == branch_id
        assert replay["body"]["branch_id"] == branch_id
        assert replay["body"]["replay_status"] == "REGISTERED_REPLAY_VERIFIED"
        assert replay["body"]["workload_rerun"] is False
        assert (
            replay["body"]["decision_registration_digest"]
            == replay["parent_digests"][2]
        )
    for decision in (records[1]["decision"], records[2]["decision"]):
        assert (
            decision["body"]["terminal_decision"] == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
        )
        assert decision["body"]["scientific_decision"] is None
        assert decision["body"]["evaluation_status"] == "NOT_RUN_PARENT_NOT_ACCEPTED"
    for completion in completions:
        body = completion["body"]
        assert body["historical_outcomes_read"] == 0
        assert body["synthetic_replicate_count"] == 0
        assert body["warmup_alias_position_count"] == 0
        assert body["historical_fold_count"] == 0
        assert body["bootstrap_resample_count"] == 0
        assert body["evidence_created"] is False
        assert body["promotion_gate_opened"] is False
    assert (
        temporal_completion["body"]["registration_count_including_mainline_execution"]
        == 3
    )
    assert (
        joint_completion["body"]["registration_count_including_mainline_execution"] == 3
    )

    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "DEEPER_VALIDATION_REQUIRED"
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["durable_write_count"] == 0


def test_global_router_is_finite_categorical_and_replay_is_pure(monkeypatch) -> None:
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert route["route"] == "ADAPTIVE_RESEARCH_ELIGIBLE"
    assert route["next_lane"] == "P3_PREDICTIVE_PREREGISTRATION_FREEZE"
    assert route["route"] in routing.GLOBAL_ROUTES
    assert route["decision_replay_coverage"] == "COMPLETE"
    assert route["measurement_global_coverage"] == "FULL"
    assert route["router_conclusive_coverage"] == "FULL"
    assert set(route["decision_projection_rows"][0]) == {
        "branch_id",
        "estimand_digest",
        "decision_path",
        "terminal_decision",
        "scientific_decision",
        "evaluation_status",
        "measurement_health",
        "historical_evidence",
        "accepted_for_downstream_baseline",
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
        "decision_artifact_digest",
        "decision_producer_execution_id",
        "replay_artifact_digest",
        "replay_registration_digest",
    }

    forbidden_workload_calls = []
    for module, name in (
        (temporal, "build_temporal_warmup_index"),
        (temporal, "build_temporal_composite_view"),
        (joint, "build_q_base_checkpoint_index"),
        (joint, "build_joint_z_checkpoint_index"),
        (joint, "build_joint_target_prediction_index"),
    ):
        monkeypatch.setattr(
            module,
            name,
            lambda *_args, _name=name, **_kwargs: forbidden_workload_calls.append(
                _name
            ),
        )
    replay = routing.replay_m4_v2_global_route_decision(
        records,
        route,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert forbidden_workload_calls == []
    assert replay == {
        "status": "REPLAY_VERIFIED",
        "outer_status": "REPLAY_VERIFIED",
        "capability_status": "REGISTERED_REPLAY_VERIFIED",
        "same_route_decision_identity": True,
        "same_registered_content": True,
        "route_artifact_digest": route["artifact_digest"],
        "source_integrity_verified": True,
        "workload_rerun": False,
        "raw_history_read": False,
        "numerical_result_payload_read": False,
        "durable_write_count": 0,
        "new_fact_count": 0,
        "durable_state_changed": False,
    }
    source = inspect.getsource(routing.compile_m4_v2_global_route_decision)
    assert "repository" not in source.lower()
    assert "fold" not in source.lower()


def test_global_router_repair_and_partial_positive_never_adaptive() -> None:
    repair_records, _ = _zero_compute_records(
        marginal_evidence="INCONCLUSIVE", health="REPAIR"
    )
    repair = routing.compile_m4_v2_global_route_decision(
        repair_records,
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert repair["route"] == "MEASUREMENT_REPAIR_REQUIRED"
    assert repair["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"

    partial = routing.compile_m4_v2_global_route_decision(
        _partial_positive_records(),
        source_contract_digest=_digest("global-source"),
        task_digest=_digest("global-task"),
    )
    assert partial["positive_branches"] == ["MARGINAL_STATIC"]
    assert partial["measurement_global_coverage"] == "PARTIAL"
    assert partial["router_conclusive_coverage"] == "PARTIAL"
    assert partial["route"] == "DEEPER_VALIDATION_REQUIRED"
    assert partial["route"] != "ADAPTIVE_RESEARCH_ELIGIBLE"


def test_resolver_global_route_and_four_and_p3_barrier() -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    successor_task_keys = {
        marginal_builder.REPLAY_RECOVERY_TASK_KEY,
        *(M4_V2_SUCCESSOR_TASKS.values()),
    } - {marginal_builder.REPLAY_TASK_KEY}
    assert marginal_builder.REPLAY_RECOVERY_TASK_KEY in {
        task.task_key for task in manifest.tasks
    }
    global_task = _task(payload, global_builder.GLOBAL_TASK)
    placeholder = _task(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    predictive_p3 = _task(payload, PREDICTIVE_P3_TASK_KEY)
    assert global_task["requested_capability"] == routing.GLOBAL_ROUTE_CAPABILITY
    assert _dependency_tuples(global_task) == (
        ("artifact", global_builder.SOURCE_FACT, "available"),
        *(("artifact", fact, "available") for fact in M4_V2_SUCCESSOR_REPLAY_FACTS),
    )
    assert placeholder["requested_capability"] is None
    assert placeholder["metric_contract"]["runner"] is None
    assert placeholder["metric_contract"]["execution_authorized"] is False
    assert placeholder["completion_classification"] == "INTEGRATION_PENDING"
    assert _dependency_tuples(placeholder) == (
        ("task", global_builder.GLOBAL_TASK, "completed"),
        ("artifact", routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT, "available"),
    )
    assert _dependency_tuples(predictive_p3) == (
        *_dependency_tuples(placeholder),
        ("task", M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY, "completed"),
        ("artifact", M4_P3_PREDICTIVE_PREREGISTRATION_FACT, "available"),
    )

    for fact in M4_V2_SUCCESSOR_REPLAY_FACTS[:-1]:
        _add_facts(payload, fact)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, global_builder.GLOBAL_TASK).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _add_facts(payload, M4_V2_SUCCESSOR_REPLAY_FACTS[-1])
    for task_key in successor_task_keys - {global_builder.GLOBAL_TASK}:
        if _task(payload, task_key)["status"] != "completed":
            _set_task_completed(payload, task_key)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    successor_ready = [
        item.task_key
        for item in ResearchOSControlPlane().resolve(manifest).ready_queue
        if item.task_key in successor_task_keys
    ]
    assert successor_ready == [global_builder.GLOBAL_TASK]

    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _add_facts(payload, routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY).status
        is TaskStatus.READY
    )
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )

    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    assert M4_P3_PREDICTIVE_PREREGISTRATION_FACT not in manifest.facts.artifacts

    _add_facts(payload, M4_P3_PREDICTIVE_PREREGISTRATION_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    successor_capabilities = {
        task["requested_capability"]
        for task in payload["tasks"]
        if task["task_key"] in successor_task_keys
    }
    assert (
        _task(payload, PREDICTIVE_P3_TASK_KEY)["requested_capability"]
        not in successor_capabilities
    )


def test_p4_requires_completed_p3_and_explicit_pass() -> None:
    payload = _successor_payload()
    p4 = _task(payload, PREDICTIVE_P4_TASK_KEY)
    assert _dependency_tuples(p4) == (
        ("task", PREDICTIVE_P3_TASK_KEY, "completed"),
        ("artifact", PREDICTIVE_P3_PASS_TO_P4_FACT, "available"),
    )
    _set_task_completed(payload, global_builder.GLOBAL_TASK)
    _set_task_completed(payload, M4_P3_PREDICTIVE_PREREGISTRATION_TASK_KEY)
    _add_facts(
        payload,
        routing.ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT,
    )
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P3_TASK_KEY).status is TaskStatus.READY
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _set_task_completed(payload, PREDICTIVE_P3_TASK_KEY)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert (
        _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status
        is TaskStatus.DEPENDENCY_WAIT
    )
    _add_facts(payload, PREDICTIVE_P3_PASS_TO_P4_FACT)
    manifest = ControlPlaneManifest.from_dict(_without_manifest_digest(payload))
    assert _resolution(manifest, PREDICTIVE_P4_TASK_KEY).status is TaskStatus.READY


def test_source_contracts_exact_closure_and_digest_drift_fail_closed(
    tmp_path: Path,
) -> None:
    specs = supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS
    legacy_source_sets: dict[str, tuple[str, ...]] = {}
    for family in ("marginal", "temporal", "joint", "global"):
        contract = supervisor_module.verify_m4_v2_historical_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert len(entries) == len(set(entries)) == 7
        legacy_source_sets[family] = entries
        for item in contract["source_entries"]:
            historical_bytes = supervisor_module._m4_v2_raw_git_blob(
                root_dir=ROOT_DIR,
                commit=supervisor_module.M4_V2_HISTORICAL_SOURCE_PIN,
                path=item["path"],
            )
            assert item["sha256"] == hashlib.sha256(historical_bytes).hexdigest()

    active_source_sets: dict[str, tuple[str, ...]] = {}
    for family in ("marginal", "global"):
        contract = supervisor_module._load_m4_v2_successor_source_contract(
            root_dir=ROOT_DIR, family=family
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert len(entries) == len(set(entries)) == 7
        assert contract["artifact_digest"] == json.loads(
            SOURCE_PATHS[0 if family == "marginal" else 3].read_text(encoding="utf-8")
        )["artifact_digest"]
        active_source_sets[family] = entries
    expected_arrays = {
        "temporal": "c3aa7e4fbb5a60393e68582ebf9b47d572892b8c2a8494db8065b8a604ab1898",
        "joint": "b9d51e1feb75e656708e410c9f719d839fedc3ed5c6dc2eae9929be8bfdcb60d",
    }
    for family in ("temporal", "joint"):
        selector = specs[family]["selector"]
        contract = supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=ROOT_DIR, selector=selector
        )
        entries = tuple(item["path"] for item in contract["source_entries"])
        assert entries == tuple(specs[family]["entries"])
        assert len(entries) == len(set(entries)) == 12
        assert contract["schema_version"].endswith("source-contract.v3")
        assert contract["source_path_array_contract_version"] == 4
        assert contract["source_path_array_digest"] == expected_arrays[family]
        assert contract["accepted_support_input_schema"] == (
            "dehps-m4-v2-accepted-support-input.v3"
        )
        assert all(
            item["sha256"]
            == hashlib.sha256((ROOT_DIR / item["path"]).read_bytes()).hexdigest()
            for item in contract["source_entries"]
        )
        active_source_sets[family] = entries

    for rejected_selector in (
        "marginal",
        "global",
        "temporal",
        "joint",
        "temporal_v2",
        "joint_v2",
    ):
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="selector is not authorized",
        ):
            supervisor_module.load_m4_v2_active_successor_source_contract(
                root_dir=ROOT_DIR, selector=rejected_selector
            )

    assert "branch_decision" not in {
        node.module
        for module in (temporal, joint, routing)
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert M4V2BranchDecisionArtifact.__module__ == "dehps.research_os.models"

    family = "temporal"
    spec = specs[family]
    for entry in supervisor_module.load_m4_v2_active_successor_source_contract(
        root_dir=ROOT_DIR, selector=spec["selector"]
    )["source_entries"]:
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], target)
    contract_target = tmp_path / spec["path"]
    contract_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_DIR / spec["path"], contract_target)
    first_source = tmp_path / spec["entries"][0]
    first_source.write_bytes(first_source.read_bytes() + b"\n# digest drift\n")
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="source bytes changed"
    ):
        supervisor_module.load_m4_v2_active_successor_source_contract(
            root_dir=tmp_path, selector=spec["selector"]
        )

    original_raw_git_blob = supervisor_module._m4_v2_raw_git_blob

    def tampered_historical_blob(*, root_dir: Path, commit: str, path: str) -> bytes:
        content = original_raw_git_blob(root_dir=root_dir, commit=commit, path=path)
        if path == legacy_source_sets["joint"][0]:
            return content + b"\n# historical tamper\n"
        return content

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            supervisor_module, "_m4_v2_raw_git_blob", tampered_historical_blob
        )
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="historical source bytes changed",
        ):
            supervisor_module.verify_m4_v2_historical_successor_source_contract(
                root_dir=ROOT_DIR, family="joint"
            )


def test_successor_v2_estimator_identity_rejects_predecessor_v1() -> None:
    payload = _successor_payload()
    temporal_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-temporal-marginal-increment")
    ]
    joint_tasks = [
        item
        for item in payload["tasks"]
        if item["task_key"].startswith("m4-v2-joint-residual-increment")
    ]
    assert temporal_tasks and joint_tasks
    temporal_source = json.loads(SOURCE_PATHS[1].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    joint_source = json.loads(SOURCE_PATHS[2].read_text(encoding="utf-8"))[
        "artifact_digest"
    ]
    assert all(item["input_artifact_digests"] == [temporal_source] for item in temporal_tasks)
    assert all(item["input_artifact_digests"] == [joint_source] for item in joint_tasks)
    assert all(
        item["metric_contract"]["estimator_id"] == temporal.TEMPORAL_MODEL_ID
        for item in temporal_tasks
    )
    assert all(
        item["metric_contract"]["estimator_id"] == joint.JOINT_ESTIMATOR_ID
        for item in joint_tasks
    )
    assert joint.REQUEST481_PREDECESSOR_ESTIMATOR_ID != joint.JOINT_ESTIMATOR_ID
    assert (
        temporal.REQUEST481_PREDECESSOR_JOINT_ESTIMATOR_ID
        != temporal.SUCCESSOR_JOINT_ESTIMATOR_ID
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["selector"]
        == "temporal_v3"
    )
    assert (
        supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["selector"]
        == "joint_v3"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["temporal"]["path"].endswith(
        "source-v3.json"
    )
    assert supervisor_module.M4_V2_SUCCESSOR_SOURCE_SPECS["joint"]["path"].endswith(
        "source-v3.json"
    )


def _warmup_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rule = temporal.build_transition_local_warmup_rule()
    rows = []
    for ordinal in range(temporal.WARMUP_START, temporal.WARMUP_END + 1):
        checkpoint = temporal.build_strict_prior_marginal_checkpoint(
            transition_ordinal=ordinal,
            issue=f"issue-{ordinal}",
            prefix_last_issue=f"issue-{ordinal - 1}",
            prefix_outcome_chain_digest=_digest(f"prefix-{ordinal}"),
            q_m_marginal_content_digest=_digest(f"qm-marginal-{ordinal}"),
            q_m_full_distribution_content_digest=_digest(f"qm-full-{ordinal}"),
        )
        rows.append(temporal.build_temporal_warmup_row(checkpoint))
    return rule, rows


def test_fixed_null_warmup_exact_alias_and_falsifiers() -> None:
    rule, rows = _warmup_rows()
    index = temporal.build_temporal_warmup_index(rows, rule_digest=rule["rule_digest"])
    assert rule["transition_range"] == [2, 900]
    assert rule["transition_count"] == 899
    assert rule["theta_float_hex"] == "0x0.0p+0"
    assert rule["theta_ieee754_binary64_be_hex"] == "0000000000000000"
    assert rule["negative_zero_allowed"] is False
    assert rule["temporal_theta_fit_invoked"] is False
    assert rule["temporal_theta_root_existence_test_invoked"] is False
    assert rule["regularization"] is None
    assert rule["fallback"] is None
    assert index["row_count"] == 899
    assert [item["transition_ordinal"] for item in rows] == list(range(2, 901))
    assert all(
        item["q_t_marginal_content_digest"] == item["q_m_marginal_content_digest"]
        for item in rows
    )
    assert all(
        item["q_t_full_distribution_content_digest"]
        == item["q_m_full_distribution_content_digest"]
        for item in rows
    )
    assert all(item["temporal_theta_fit_invoked"] is False for item in rows)

    for field, changed in (
        ("theta_float_hex", "-0x0.0p+0"),
        ("theta_float_hex", "0x1.0000000000000p-1"),
        ("temporal_theta_fit_invoked", True),
        ("q_t_full_distribution_content_digest", _digest("reconstructed-q-t")),
    ):
        tampered = copy.deepcopy(rows[0])
        tampered[field] = changed
        with pytest.raises(temporal.TemporalMarginalIncrementContractError):
            temporal.validate_temporal_warmup_row(tampered)
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(rows[:-1], rule_digest=rule["rule_digest"])
    duplicated = [*rows[:-1], rows[-2]]
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="coverage_or_order"
    ):
        temporal.build_temporal_warmup_index(
            duplicated, rule_digest=rule["rule_digest"]
        )

    same_prefix = dict(rows[10])
    same_prefix["non_identity_suffix_provenance"] = "changed"
    temporal.assert_temporal_suffix_noninterference(rows[10], same_prefix)
    changed_prefix = dict(rows[10])
    changed_prefix["q_m_full_distribution_content_digest"] = _digest("suffix-leak")
    with pytest.raises(temporal.TemporalMarginalIncrementContractError, match="suffix"):
        temporal.assert_temporal_suffix_noninterference(rows[10], changed_prefix)
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=0, replicate_index=0, transition_ordinal=2
        )
        == 0
    )
    assert (
        temporal.temporal_synthetic_warmup_position(
            cell_index=13, replicate_index=511, transition_ordinal=900
        )
        == 6_444_031
    )


def test_temporal_composite_and_joint_chronology_contracts() -> None:
    view = temporal.build_temporal_composite_view(
        warmup_index_digest=_digest("warmup-index"),
        accepted_temporal_evaluation_index_digest=_digest("accepted-index"),
    )
    assert view["transition_range"] == [2, 3481]
    assert view["row_count"] == 3480
    assert temporal.temporal_checkpoint_plan(900).theta_fit_invoked is False
    assert temporal.temporal_checkpoint_plan(901).prefix_last_ordinal == 900
    assert temporal.temporal_checkpoint_plan(901).theta_fit_invoked is True
    assert temporal.temporal_checkpoint_plan(902).prefix_last_ordinal == 901
    assert joint.joint_checkpoint_plan(901).eta_training_range == (2, 900)
    assert joint.joint_checkpoint_plan(901).eta_training_count == 899
    assert joint.joint_checkpoint_plan(902).eta_training_range == (2, 901)
    assert joint.joint_checkpoint_plan(902).eta_training_count == 900
    assert joint.joint_checkpoint_plan(902).target_z_may_be_reconstructed is False


def test_synthetic_cartesian_grid_seed_and_count_invariance() -> None:
    expected_counts = {
        "cell_count": 14,
        "replicates_per_cell": 512,
        "synthetic_replicate_count": 7168,
        "synthetic_generated_issue_count": 15_920_128,
        "outer_evaluation_issue_count": 9_468_928,
        "bootstrap_resample_count": 14_651_392,
        "historical_fold_count": 2581,
        "historical_child_count": 16_000,
        "warmup_transition_count_per_replicate": 899,
        "warmup_alias_position_count": 6_444_032,
    }
    assert dict(temporal.PLANNED_COUNTS) == expected_counts
    assert dict(joint.PLANNED_COUNTS) == expected_counts
    assert temporal.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert joint.SYNTHETIC_WARMUP_RNG_CALL_COUNT == 0
    assert temporal.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert joint.SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP is False
    assert temporal.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False
    assert joint.SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD is False

    health = _digest("health-contract")
    seed = _digest("seed-contract")
    temporal_coordinates = [
        temporal.build_temporal_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    joint_coordinates = [
        joint.build_joint_synthetic_sequence_coordinate(
            health_contract_digest=health,
            seed_contract_digest=seed,
            cell_index=cell,
            replicate_index=replicate,
        )
        for cell in range(14)
        for replicate in range(512)
    ]
    assert len(temporal_coordinates) == len(joint_coordinates) == 7168
    assert len({item["coordinate_digest"] for item in temporal_coordinates}) == 7168
    assert len({item["coordinate_digest"] for item in joint_coordinates}) == 7168
    assert {item["coordinate_digest"] for item in temporal_coordinates}.isdisjoint(
        item["coordinate_digest"] for item in joint_coordinates
    )
    assert all(
        item["seed_contract_digest"] == seed
        for item in temporal_coordinates + joint_coordinates
    )
    assert all(
        item["sequence_seed_full_sha256"] != seed
        for item in temporal_coordinates + joint_coordinates
    )
    tampered = copy.deepcopy(temporal_coordinates[0])
    tampered["sequence_seed_full_sha256"] = _digest("seed-drift")
    with pytest.raises(
        temporal.TemporalMarginalIncrementContractError, match="seed_or_cell"
    ):
        temporal.validate_temporal_synthetic_sequence_coordinate(tampered)


def test_all_17_artifact_types_nested_lineage_paths_and_cardinalities() -> None:
    assert len(M4_V2_ARTIFACT_TYPE_REGISTRY) == 17
    assert set(M4_V2_ARTIFACT_TYPE_REGISTRY) == EXPECTED_ARTIFACT_TYPES
    assert len(M4_V2_NESTED_SCHEMA_REGISTRY) == 46
    assert all(spec.body_fields for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values())
    assert all(
        len(spec.body_fields) == len(set(spec.body_fields))
        for spec in M4_V2_ARTIFACT_TYPE_REGISTRY.values()
    )

    records, completions = _zero_compute_records()
    for record in records:
        for artifact_name in ("decision", "replay"):
            envelope = record[artifact_name]
            validate_m4_v2_artifact_envelope(envelope)
            missing = copy.deepcopy(envelope)
            missing.pop("parent_digests")
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(missing)
            extra = copy.deepcopy(envelope)
            extra["sidecar"] = {}
            with pytest.raises(ResearchOSValidationError):
                validate_m4_v2_artifact_envelope(extra)
    eighteenth = copy.deepcopy(records[0]["decision"])
    eighteenth["artifact_type"] = "M4V2ForbiddenEighteenthArtifact"
    with pytest.raises(ResearchOSValidationError, match="unknown"):
        validate_m4_v2_artifact_envelope(eighteenth)

    assert temporal.temporal_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert joint.joint_registration_plan(
        "PARENT_NOT_ACCEPTED"
    ).artifact_types_in_registration_order == (
        "M4V2BranchDecisionArtifact",
        "M4V2JointResidualProducerCompletionArtifact",
        "research_os_mainline_execution",
    )
    assert (
        temporal.temporal_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 6
    )
    assert (
        joint.joint_registration_plan(
            "EVALUATED_COMPLETE"
        ).registration_count_including_mainline_execution
        == 7
    )
    for completion in completions:
        assert (
            completion["artifact_digest"]
            not in completion["body"]["registered_artifact_digests_in_order"]
        )

    q_digest = _digest("q")
    certificate = joint.build_q_base_reconstruction_certificate(
        transition_ordinal=2,
        temporal_support_row_digest=_digest("temporal-row"),
        q_t_full_distribution_content_digest=q_digest,
        q_base_full_distribution_content_digest=q_digest,
        max_probability_difference_float_hex="0x0.0p+0",
        max_marginal_difference_float_hex="0x0.0p+0",
        normalization_residual_float_hex="0x0.0p+0",
    )
    checkpoint = joint.build_q_base_checkpoint(
        transition_ordinal=2,
        issue="issue-2",
        temporal_support_row_digest=_digest("temporal-row"),
        temporal_composite_view_digest=_digest("temporal-view"),
        q_t_marginal_content_digest=_digest("q-marginal"),
        q_t_full_distribution_content_digest=q_digest,
        baseline_contract_digest=_digest("baseline-contract"),
        reconstruction_certificate=certificate,
    )
    assert checkpoint["q_base_full_distribution_content_digest"] == q_digest
    drift = copy.deepcopy(checkpoint)
    drift["q_base_full_distribution_content_digest"] = _digest("qbase-drift")
    with pytest.raises(joint.JointResidualIncrementContractError, match="alias"):
        joint.validate_q_base_checkpoint(drift)
    coordinate = joint.build_certificate_coordinate_identity(
        scope="HISTORICAL_Z",
        source_contract_digest=_digest("joint-source"),
        preregistration_artifact_digest=_digest("joint-prereg"),
        producer_execution_id=_digest("joint-producer"),
        transition_ordinal=2,
        issue_or_sequence_coordinate_digest="issue-2",
        support_kind="WARMUP_NULL_ALIAS",
    )
    validate_m4_v2_nested_schema("certificate_coordinate_identity", coordinate)
    coordinate_drift = copy.deepcopy(coordinate)
    coordinate_drift["transition_ordinal"] = 3
    with pytest.raises(joint.JointResidualIncrementContractError):
        joint.validate_certificate_coordinate_identity(coordinate_drift)

    execution_id = _digest("global-execution")
    artifact_digest = _digest("global-route-artifact")
    expected_path = (
        f"runtime/research-os/mainline/tasks/{routing.GLOBAL_ROUTE_TASK_KEY}/"
        f"{execution_id}/artifacts/global-routing-decision/{artifact_digest}/decision.json"
    )
    assert (
        routing.m4_v2_global_route_artifact_path(
            execution_id=execution_id, artifact_digest=artifact_digest
        )
        == expected_path
    )


def test_holm_lineage_and_formal_one_rules_fail_before_workload() -> None:
    exact = temporal.validate_accepted_parent_raw_p_lineage(
        parent_branch_id="MARGINAL_STATIC",
        terminal_decision="BRANCH_INFORMATION_ACCEPTED",
        accepted_for_downstream_baseline=True,
        historical_artifact_digest=temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
        historical_registration_digest=temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
        producer_execution_id=_digest("marginal-producer"),
        replay_status="REGISTERED_REPLAY_VERIFIED",
        raw_primary_p_value=0.125,
    )
    assert exact == 0.125
    for changed in (
        {"historical_artifact_digest": _digest("missing-historical")},
        {"historical_registration_digest": _digest("missing-registration")},
        {"replay_status": "REPLAY_VERIFIED"},
        {"accepted_for_downstream_baseline": False},
    ):
        arguments = {
            "parent_branch_id": "MARGINAL_STATIC",
            "terminal_decision": "BRANCH_INFORMATION_ACCEPTED",
            "accepted_for_downstream_baseline": True,
            "historical_artifact_digest": temporal.MARGINAL_RAW_P_ARTIFACT_DIGEST,
            "historical_registration_digest": temporal.MARGINAL_RAW_P_REGISTRATION_DIGEST,
            "producer_execution_id": _digest("marginal-producer"),
            "replay_status": "REGISTERED_REPLAY_VERIFIED",
            "raw_primary_p_value": 0.125,
            **changed,
        }
        with pytest.raises(
            temporal.TemporalMarginalIncrementContractError, match="lineage"
        ):
            temporal.validate_accepted_parent_raw_p_lineage(**arguments)
    assert (
        temporal.validate_temporal_holm_family(
            {
                "MARGINAL_STATIC": 0.125,
                "TEMPORAL_MARGINAL_INCREMENT": 0.25,
                "JOINT_RESIDUAL_INCREMENT": 1.0,
            },
            marginal_raw_p_value=0.125,
            temporal_raw_p_value=0.25,
        )["JOINT_RESIDUAL_INCREMENT"]
        == 1.0
    )
    assert joint.formal_holm_one_allowed(
        branch_id="JOINT_RESIDUAL_INCREMENT",
        terminal_decision=None,
        replay_status=None,
        temporal_is_current_evaluated_branch=True,
        joint_has_formally_not_run=True,
    )
    for terminal in (
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
    ):
        assert joint.formal_holm_one_allowed(
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
            terminal_decision=terminal,
            replay_status="REGISTERED_REPLAY_VERIFIED",
        )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="NO_DETECTABLE_INFORMATION",
        replay_status="REGISTERED_REPLAY_VERIFIED",
    )
    assert not joint.formal_holm_one_allowed(
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        terminal_decision="INVALID_EXECUTION",
        replay_status=None,
    )


def test_supervisor_global_replay_is_zero_write_and_preserves_all_identities(
    monkeypatch,
) -> None:
    payload = _successor_payload()
    manifest = ControlPlaneManifest.from_dict(payload)
    before_manifest = m4_v2_canonical_json(manifest.to_dict(include_digest=True))
    before_snapshot = ResearchOSControlPlane().resolve(manifest)
    before_ready = m4_v2_canonical_json(jsonable(before_snapshot.ready_queue))
    records = _accepted_records()
    route = routing.compile_m4_v2_global_route_decision(
        records,
        source_contract_digest=_digest("global-source"),
        task_digest=next(
            task
            for task in manifest.tasks
            if task.task_key == routing.GLOBAL_ROUTE_TASK_KEY
        ).artifact_digest,
    )

    class ReadOnlyRepository:
        def __init__(self):
            self.loads = 0
            self.writes: list[str] = []
            self.control_plane = ResearchOSControlPlane()

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            self.loads += 1
            return manifest

        def __getattr__(self, name: str):
            if any(
                token in name
                for token in (
                    "record",
                    "import",
                    "write",
                    "register",
                    "update",
                    "append",
                )
            ):

                def forbidden(*_args, **_kwargs):
                    self.writes.append(name)
                    raise AssertionError(f"durable write attempted: {name}")

                return forbidden
            raise AttributeError(name)

    repository = ReadOnlyRepository()
    execution_id = _digest("global-execution")
    execution_artifact = {
        "execution_id": execution_id,
        "artifact_digest": _digest("global-execution-artifact"),
    }
    registrations = [
        {"artifact_type": routing.GLOBAL_ROUTE_ARTIFACT_TYPE},
        {"artifact_type": "research_os_mainline_execution"},
    ]
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, execution_artifact, registrations),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_m4_v2_successor_source_contract",
        lambda **_kwargs: {"artifact_digest": _digest("global-source")},
    )
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_source",
        lambda _self, _family, _task: {"artifact_digest": _digest("global-source")},
    )
    by_decision_task = {
        M4_V2_SUCCESSOR_TASKS["marginal_decision"]: records[0],
        temporal.TEMPORAL_PRODUCER_TASK_KEY: records[1],
        joint.JOINT_PRODUCER_TASK_KEY: records[2],
    }
    monkeypatch.setattr(
        supervisor_module.M4V2SuccessorCapability,
        "_branch_record",
        lambda _self, **kwargs: by_decision_task[kwargs["decision_task_key"]],
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **_kwargs: route,
    )
    supervisor = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
    supervisor.repository = repository
    supervisor.root_dir = ROOT_DIR
    supervisor.control_plane_key = CONTROL_PLANE_KEY
    status_projection_calls: list[str] = []
    monkeypatch.setattr(
        supervisor,
        "_build_lane_status",
        lambda current_manifest, **kwargs: (
            status_projection_calls.append(current_manifest.artifact_digest)
            or {
                "manifest_digest": current_manifest.artifact_digest,
                "snapshot_digest": kwargs["snapshot"].snapshot_digest,
                "ready_queue": jsonable(kwargs["snapshot"].ready_queue),
            }
        ),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("state write")),
    )
    monkeypatch.setattr(
        supervisor,
        "_write_lane_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("lane write")),
    )
    replay = supervisor.replay(task_key=routing.GLOBAL_ROUTE_TASK_KEY)
    assert replay["status"] == "REPLAY_VERIFIED"
    assert (
        replay["capability_replay"]["capability_status"] == "REGISTERED_REPLAY_VERIFIED"
    )
    assert replay["capability_replay"]["workload_rerun"] is False
    assert replay["durable_state_changed"] is False
    assert repository.writes == []
    assert status_projection_calls == [manifest.artifact_digest]
    assert (
        m4_v2_canonical_json(manifest.to_dict(include_digest=True)) == before_manifest
    )
    after_snapshot = ResearchOSControlPlane().resolve(manifest)
    assert after_snapshot.snapshot_digest == before_snapshot.snapshot_digest
    assert m4_v2_canonical_json(jsonable(after_snapshot.ready_queue)) == before_ready


class _RegistrationCursor:
    def __init__(self, stored: Mapping[str, Any] | None) -> None:
        self.stored = None if stored is None else copy.deepcopy(dict(stored))
        self._last = ""

    def execute(self, sql: str, _params: Any):
        self._last = " ".join(sql.split())
        return self

    def fetchone(self):
        if "SELECT registration_json" in self._last:
            return None if self.stored is None else {"registration_json": self.stored}
        raise AssertionError(self._last)


def test_atomic_publication_crash_reconciliation_and_conflicts(
    tmp_path: Path, monkeypatch
) -> None:
    staged = tmp_path / ".staging" / "00.json"
    content = b'{"frozen":true}\n'
    fsync_calls: list[int] = []
    real_fsync = os.fsync

    def observed_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(supervisor_module.os, "fsync", observed_fsync)
    supervisor_module._atomic_write_staged_file(staged, content)
    assert staged.read_bytes() == content
    assert len(fsync_calls) >= 2
    with pytest.raises(FileExistsError):
        supervisor_module._atomic_write_staged_file(staged, content)

    destination = tmp_path / "canonical" / "artifact.json"
    ownership = supervisor_module._atomic_publish_noreplace(staged, destination)
    assert ownership[2] is True
    assert not staged.exists()
    assert destination.read_bytes() == content

    identical_stage = tmp_path / ".staging" / "01.json"
    supervisor_module._atomic_write_staged_file(identical_stage, content)
    preexisting = supervisor_module._atomic_publish_noreplace(
        identical_stage, destination
    )
    assert preexisting[2] is False
    assert identical_stage.exists()
    mismatch_stage = tmp_path / ".staging" / "02.json"
    supervisor_module._atomic_write_staged_file(mismatch_stage, b"different\n")
    with pytest.raises(supervisor_module.MainlineSupervisorError, match="collision"):
        supervisor_module._atomic_publish_noreplace(mismatch_stage, destination)
    assert destination.read_bytes() == content

    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {destination: ownership}
    )
    assert not destination.exists()
    preserved = tmp_path / "canonical" / "preexisting.json"
    preserved.parent.mkdir(parents=True, exist_ok=True)
    preserved.write_bytes(content)
    stat = preserved.stat()
    supervisor_module.ResearchEvidenceSupervisor._cleanup_owned_atomic_paths(
        {preserved: (stat.st_dev, stat.st_ino, False)}
    )
    assert preserved.exists()

    registration = MainlineArtifactRegistration(
        execution_id=_digest("execution"),
        control_plane_key=CONTROL_PLANE_KEY,
        task_key="task",
        task_digest=_digest("task"),
        artifact_digest=_digest("artifact"),
        artifact_type="artifact",
        schema_version="v1",
        artifact_path="runtime/research-os/mainline/tasks/task/artifact.json",
        parent_digests=(_digest("parent"),),
        git_commit=GIT_COMMIT,
    )
    exact = jsonable(registration)
    supervisor_module._atomic_insert_registration(
        _RegistrationCursor(exact), registration
    )
    mismatch = dict(exact)
    mismatch["artifact_path"] = "mismatch"
    with pytest.raises(
        supervisor_module.MainlineSupervisorError, match="not idempotent"
    ):
        supervisor_module._atomic_insert_registration(
            _RegistrationCursor(mismatch), registration
        )

    class ReconciliationRepository:
        def __init__(
            self,
            *,
            head_digest: str,
            registrations: Sequence[Mapping[str, Any]],
            completed_event_count: int,
        ) -> None:
            self.head_digest = head_digest
            self.registrations = list(registrations)
            self.completed_event_count = completed_event_count

        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            return SimpleNamespace(artifact_digest=self.head_digest)

        def list_mainline_execution_events(self, **_kwargs):
            return [
                {"event_type": "completed"} for _ in range(self.completed_event_count)
            ]

        def list_mainline_artifacts(self, **_kwargs):
            return copy.deepcopy(self.registrations)

    expected_row = {
        "registration_digest": registration.registration_digest,
        **jsonable(registration),
    }
    head = _digest("head")
    complete = _digest("complete")
    task = SimpleNamespace(task_key="task")

    def reconcile(repository: Any) -> str:
        instance = object.__new__(supervisor_module.ResearchEvidenceSupervisor)
        instance.repository = repository
        instance.root_dir = ROOT_DIR
        instance.control_plane_key = CONTROL_PLANE_KEY
        return instance._reconcile_atomic_completion(
            task=task,
            execution_id=registration.execution_id,
            expected_head_manifest_digest=head,
            completed_manifest_digest=complete,
            expected_registrations=(registration,),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: ({}, {}, []),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "COMMITTED"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=head,
                registrations=[],
                completed_event_count=0,
            )
        )
        == "ABSENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=0,
            )
        )
        == "INCIDENT"
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_kwargs: (_ for _ in ()).throw(
            supervisor_module.MainlineSupervisorError("registered file missing")
        ),
    )
    assert (
        reconcile(
            ReconciliationRepository(
                head_digest=complete,
                registrations=[expected_row],
                completed_event_count=1,
            )
        )
        == "INCIDENT"
    )

    source = inspect.getsource(
        supervisor_module.ResearchEvidenceSupervisor._complete_atomic_capability
    )
    assert source.count("connection.commit()") == 1
    assert source.index("_atomic_publish_noreplace") < source.index(
        "connection.commit()"
    )
    assert "self.repository.connection_factory()" in source
    repository_source = inspect.getsource(
        PostgresResearchOSRepository.import_manifest
    )
    assert repository_source.index(
        "_verify_m4_v2_failed_task_recovery_import"
    ) < repository_source.index("_verify_mainline_completion_records")


def test_engineering_boundary_has_zero_runtime_or_operator_actions() -> None:
    changed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any(" runtime/" in line or line.endswith(" runtime") for line in changed)
    assert not any("data/output" in line for line in changed)
    for builder in (
        marginal_builder.build_manifest,
        temporal_builder.build_manifest,
        joint_builder.build_manifest,
        global_builder.build_manifest,
    ):
        source = inspect.getsource(builder)
        assert "import_manifest" not in source
        assert "run_once" not in source
        assert "promotion" not in source.lower() or "promotion_gate_opened" in source
    successor = supervisor_module.M4V2SuccessorCapability
    assert not hasattr(successor, "promote")
    assert (
        M4_P3_PREDICTIVE_PREREGISTRATION_FACT
        not in _successor_payload()["facts"]["artifacts"]
    )
